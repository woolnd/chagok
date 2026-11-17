"""근거 루프: 만든 문제를 검사 AI가 근거·명확함으로 판정하고, 탈락이면 다시 만든다.

흐름
    Question (generate가 만든 문제) + 조각 3개
      │ check            검사 AI → 문장마다 근거 있나 + 명확한가 → Verdict
      │ Verdict.passed   근거·명확함 둘 다 통과인가
      │ feedback         탈락 이유를 글로 → 다시 만들 때 generate에 넘김
      ▼
    make_question        생성 → 검사 → (탈락이면 이유 넣어 다시 생성, 최대 MAX_RETRIES번) → 통과 문제 또는 None(버림)

규칙 (기획서 처음 값)
    - 기준 2개만, 통과/탈락: 근거(모범 답안 문장마다 노트에 있나), 명확함(무엇을 답할지 분명한가)
    - 하나라도 탈락이면 이유를 알려주고 다시 만든다. 최대 2번, 계속 실패하면 버린다
    - 검사 AI는 생성 AI와 다른 지시문을 쓴다
    - 난이도·채점 포인트는 검사하지 않는다
    - 검사 AI는 Claude로 시작. Claude vs Jev는 3단계에서 내 판단과 더 맞는 쪽으로 정한다
"""

import anthropic  # Claude API
from pydantic import BaseModel  # 출력 형식 (판정)

from chagok.generate import MAX_TOKENS, Question, format_chunks, generate

CHECK_MODEL = "claude-haiku-5-5"
MAX_RETRIES = 2  # 처음 1번 + 다시 만들기 2번 = 최대 3번 생성

# 검사 지시문 초안. 생성 지시문(SYSTEM)과 따로 둔다
CHECK_SYSTEM = """너는 복습 문제를 검사하는 검사자다. 문제를 고치지 말고 판정만 한다.
아래 두 기준으로만 본다. 난이도나 채점 포인트는 보지 않는다.

1. 근거: 모범 답안을 문장 단위로 나누고, 문장마다 노트 조각에 실제로 있는 내용인지 본다.
   - 노트에 있는 내용을 다른 말로 바꿔 쓴 것은 근거 있음이다.
   - 노트에 없는 사실(연도, 인물, 역사, 노트에 없는 수치나 설명)이 들어 있으면 근거 없음이다.
   - 근거 있음이면 그 문장의 근거가 된 노트 원문을 그대로 인용한다.
2. 명확함: 질문만 읽고 무엇을 답해야 할지 분명한지 본다.
   - "아는 대로 설명하시오"처럼 범위가 정해지지 않았거나, 답이 여러 방향으로 갈 수 있으면 탈락이다.
   - 질문에 노트를 봐야만 알 수 있는 지칭(예: "모델 2", "위 그림")이 있으면 탈락이다. 질문은 노트 없이 메일로만 받는다.
   - 탈락이면 무엇이 애매한지 짧게 쓴다."""


class SentenceCheck(BaseModel):
    """모범 답안 문장 하나의 근거 판정."""

    sentence: str  # 모범 답안 문장
    grounded: bool  # 노트에 있는 내용인가
    quote: str  # 근거가 된 노트 원문 (없으면 빈 문자열)


class Verdict(BaseModel):
    """검사 결과. 근거는 문장마다 판정하고, 하나라도 근거 없음이면 근거 탈락."""

    sentences: list[SentenceCheck]
    clear: bool  # 명확함 통과인가
    clear_reason: str  # 명확함 탈락 이유 (통과면 빈 문자열)

    @property
    def grounded(self) -> bool:
        """근거 통과: 모든 문장이 근거 있음."""
        return all(s.grounded for s in self.sentences)

    @property
    def passed(self) -> bool:
        """근거·명확함 둘 다 통과."""
        return self.clear and self.grounded


def check(
    question: Question, chunks: list[dict], client: anthropic.Anthropic
) -> Verdict:
    """문제 + 조각 → 검사 AI → Verdict.

    - system=CHECK_SYSTEM, user 메시지 = 노트 조각(format_chunks) + 질문 + 모범 답안
    - 채점 포인트는 넣지 않는다 (검사 대상이 아님)
    - client.messages.parse(..., output_format=Verdict), generate와 같은 stop_reason 확인
    """
    user = (
        f"[노트 조각]\n{format_chunks(chunks)}\n\n"
        f"[질문]\n{question.question}\n\n"
        f"[모범 답안]\n{question.answer}"
    )

    response = client.messages.parse(
        model=CHECK_MODEL,
        max_tokens=MAX_TOKENS,
        system=CHECK_SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_format=Verdict,
    )
    if response.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"검사 실패 ({response.stop_reason}): {question.question}")

    return response.parsed_output


def feedback(verdict: Verdict) -> str:
    """탈락 이유를 생성 AI에게 줄 글로 만든다.

    예:
        근거 없음: "1969년 민스키와 페퍼트가 지적해 ..." → 노트에 없는 내용
        명확함 탈락: 설명할 범위가 정해지지 않음
    """
    lines = []

    for s in verdict.sentences:
        if s.grounded:
            continue
        lines.append(f'근거 없음: "{s.sentence}" -> 노트에 없는 내용')

    if not verdict.clear:
        lines.append(f"명확함 탈락: {verdict.clear_reason}")
    return "\n".join(lines)


def make_question(
    concept: str, chunks: list[dict], examples: list[dict], client: anthropic.Anthropic
) -> tuple[Question | None, list[Verdict]]:
    """생성 → 검사 → 탈락이면 feedback을 넣어 다시 생성. 최대 MAX_RETRIES번 다시 만든다.

    출력: (통과한 문제 또는 None(버림), 시도마다의 Verdict 목록)
      - Verdict 목록은 "다시 만든 비율" 같은 운영 지표용
      - generate에 feedback 인자가 필요함 (아래 참고)
    """
    verdicts = []
    reason = ""

    for _ in range(MAX_RETRIES + 1):
        question = generate(concept, chunks, examples, client, feedback=reason)
        verdict = check(question, chunks, client)
        verdicts.append(verdict)
        if verdict.passed:
            return question, verdicts

        reason = feedback(verdict)

    return None, verdicts


if __name__ == "__main__":
    # 1. 내 판정과 맞는지: eval/review_examples.md 20개를 검사 AI에 돌려 근거·명확함 일치율
    # 2. 개념 몇 개로 make_question 돌려 보기
    # 실행: uv run --env-file .env python -m chagok.check [개념 ...]
    #       개념을 안 주면 eval/concepts.csv 앞 3개
    import csv
    import re
    import sys

    from kiwipiepy import Kiwi
    from sentence_transformers import CrossEncoder, SentenceTransformer

    from chagok.generate import EXAMPLES, load_examples
    from chagok.search import RERANK_MAX_LEN, RERANK_MODEL, is_hit, load_store, rerank, search
    from chagok.store import EMBED_MODEL, ROOT

    # 판정·feedback은 API 없이 먼저 확인
    ok = SentenceCheck(sentence="가", grounded=True, quote="가")
    bad = SentenceCheck(sentence="1969년", grounded=False, quote="")
    assert Verdict(sentences=[ok, ok], clear=True, clear_reason="").passed
    assert not Verdict(sentences=[ok, bad], clear=True, clear_reason="").passed
    assert not Verdict(sentences=[ok], clear=False, clear_reason="애매함").passed
    assert feedback(Verdict(sentences=[ok, bad], clear=False, clear_reason="애매함")).count("\n") == 1

    chunks, docs, index = load_store()
    client = anthropic.Anthropic()

    # 1. 예시 20개: 출처 → 조각, 내 근거·명확함 판정과 비교
    def get(block: str, name: str) -> str:
        return re.search(rf"^- {name}: (.*)", block, re.M).group(1).strip()

    text = EXAMPLES.read_text(encoding="utf-8")
    blocks = re.split(r"^## ", text, flags=re.M)[1:]
    same = {"근거": 0, "명확함": 0}
    misses = []
    for block in blocks:
        rid = block.split(" · ")[0]
        # "a.md#제목 > 4. 소제목 > X; 5. 다른 소제목" → 뒤쪽은 앞의 "a.md#제목"을 붙여 완성
        sources = get(block, "출처").split("; ")
        head = sources[0].split(" > ")[0]
        sources = [s if "#" in s else f"{head} > {s}" for s in sources]
        found = [ch for ch in chunks if is_hit(ch["id"], sources)]
        assert found, (rid, sources)

        q = Question(question=get(block, "질문"), answer=get(block, "모범 답안"), points=[])
        v = check(q, found, client)
        mine = {"근거": get(block, "근거") == "통과", "명확함": get(block, "명확함") == "통과"}
        ai = {"근거": v.grounded, "명확함": v.clear}
        for k in same:
            if mine[k] == ai[k]:
                same[k] += 1
            else:
                why = [s.sentence for s in v.sentences if not s.grounded] if k == "근거" else [v.clear_reason]
                misses.append(f"  {rid} {k}: 나 {'통과' if mine[k] else '탈락'} / AI {'통과' if ai[k] else '탈락'} {why}")

    n = len(blocks)
    assert n == 20, n
    print(f"예시 {n}개 · 내 판정과 일치: 근거 {same['근거']}/{n}, 명확함 {same['명확함']}/{n}")
    print("\n".join(misses) or "  다른 판정 없음")

    # 2. 생성 → 검사 → 다시 만들기
    if sys.argv[1:]:
        concepts = sys.argv[1:]
    else:
        with open(ROOT / "eval" / "concepts.csv", encoding="utf-8") as f:
            concepts = [row["concept"] for row in csv.DictReader(f)][:3]

    examples = load_examples(EXAMPLES)
    kiwi = Kiwi()
    model = SentenceTransformer(EMBED_MODEL)
    reranker = CrossEncoder(RERANK_MODEL, max_length=RERANK_MAX_LEN)

    for concept in concepts:
        found = rerank(concept, search(concept, kiwi, model, chunks, docs, index), reranker)
        q, verdicts = make_question(concept, found, examples, client)
        assert 1 <= len(verdicts) <= MAX_RETRIES + 1

        print(f"\n=== {concept} · 시도 {len(verdicts)}번 → {'통과' if q else '버림'}")
        for i, v in enumerate(verdicts, start=1):
            if not v.passed:
                print(f"  {i}번 탈락:\n    " + feedback(v).replace("\n", "\n    "))
        if q:
            print(f"질문: {q.question}")
            print(f"모범 답안: {q.answer}")
            print(f"채점 포인트: {' / '.join(q.points)}")
    print("\nOK")

"""검색 루프: 찾아온 조각으로 문제를 만들 수 있을 만큼 충분한지 AI가 보고, 부족하면 검색어를 바꿔 다시 찾는다.

흐름
    "기울기 소실"
      │ find             검색 → 리랭크 → 조각 3개 (search.py)
      │ judge            AI가 조각마다 관련 있나 + 전체가 충분한가 → Judgment (부족하면 새 검색어도)
      │ Judgment.enough  충분한가
      ▼
    retrieve             찾기 → 판단 → (부족하면 새 검색어로 다시 찾기, 최대 MAX_RETRIES번) → 조각 또는 None(노트 부족)

규칙 (기획서 처음 값)
    - AI가 조각마다 관련 있는지 보고, 문제를 만들 만큼 충분한지 판단한다
    - 부족하면 검색어를 바꿔 다시 찾는다. 최대 2번
    - 그래도 부족하면 "노트가 부족한 개념"으로 표시하고 넘어간다
    - 지표: 문맥 정밀도 = 관련 있는 조각 수 ÷ 찾아온 조각 수 (AI 판정, 계산은 코드)
"""

from collections.abc import Callable  # find 함수 타입

import anthropic  # Claude API
from pydantic import BaseModel  # 출력 형식 (판단)

from chagok.generate import MAX_TOKENS, format_chunks

RETRIEVE_MODEL = "claude-haiku-5-5"
MAX_RETRIES = 2  # 처음 1번 + 다시 찾기 2번 = 최대 3번 검색

# 판단 지시문 초안. 생성·검사 지시문과 따로 둔다
RETRIEVE_SYSTEM = """너는 복습 문제를 만들기 전에 노트 조각을 살펴보는 검토자다.
개념 하나와 검색으로 찾아온 노트 조각들을 보고 두 가지를 판단한다.
노트 조각은 "출처:" 줄로 시작하는 덩어리 하나가 한 개다. 안의 ### 소제목으로 나누지 말고, 조각 수만큼만 판정하며, id는 출처를 그대로 쓴다.

1. 조각마다: 이 개념을 설명하는 내용이 들어 있는가. 이름만 스치듯 나오면 관련 없음이다.
2. 전체: 관련 있는 조각만으로 이 개념의 서술형 문제 하나와 모범 답안을 노트 내용만으로 쓸 수 있는가.

충분하지 않으면 무엇이 빠졌는지 짧게 쓰고, 노트에서 그 내용을 찾을 새 검색어를 하나 제안한다.
새 검색어는 노트에 나올 법한 용어로, 개념 이름을 다르게 부르거나 더 구체적으로 좁힌 것이다."""


class ChunkJudge(BaseModel):
    """조각 하나의 관련 판정."""

    id: str  # 조각 id (출처)
    relevant: bool  # 이 개념을 설명하는 내용이 있나


class Judgment(BaseModel):
    """조각들 판단 결과. 충분하지 않으면 빠진 것과 새 검색어."""

    chunks: list[ChunkJudge]
    enough: bool  # 문제를 만들 만큼 충분한가
    missing: str  # 빠진 내용 (충분하면 빈 문자열)
    new_query: str  # 다시 찾을 검색어 (충분하면 빈 문자열)

    @property
    def precision(self) -> float:
        """문맥 정밀도: 관련 있는 조각 수 ÷ 조각 수."""
        count = 0
        for c in self.chunks:
            if c.relevant:
                count += 1
        return count / len(self.chunks)


def judge(concept: str, chunks: list[dict], client: anthropic.Anthropic) -> Judgment:
    """개념 + 조각 → AI → Judgment.

    - system=RETRIEVE_SYSTEM, user 메시지 = 개념 + format_chunks(조각)
    - client.messages.parse(..., output_format=Judgment), generate와 같은 stop_reason 확인
    """
    user = (
        f"[개념]\n{concept}\n\n"
        f"[노트 조각]\n{format_chunks(chunks)}\n\n"
        f'위 노트 조각이 "{concept}" 문제를 만들기에 충분한지 판단하라.'
    )

    response = client.messages.parse(
        model=RETRIEVE_MODEL,
        max_tokens=MAX_TOKENS,
        system=RETRIEVE_SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_format=Judgment,
    )

    if response.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"{concept}: 검색 판단 실패 ({response.stop_reason})")

    judgment = response.parsed_output
    if len(judgment.chunks) != len(chunks):
        raise RuntimeError(f"{concept}: 조각 {len(chunks)}개인데 판정 {len(judgment.chunks)}개")
    return judgment


def retrieve(
    concept: str, find: Callable[[str], list[dict]], client: anthropic.Anthropic
) -> tuple[list[dict] | None, list[tuple[str, Judgment]]]:
    """찾기 → 판단 → 부족하면 judgment.new_query로 다시 찾기. 최대 MAX_RETRIES번 다시 찾는다.

    - find(검색어) → 조각 3개. search + rerank를 묶은 함수를 밖에서 넘겨받는다
    - 판단은 항상 원래 개념(concept)으로 한다. 바뀌는 건 검색어뿐

    출력: (충분한 조각 또는 None(노트 부족), 시도마다 (검색어, Judgment) 목록)
    """
    tries = []
    query = concept

    for _ in range(MAX_RETRIES + 1):
        found = find(query)
        judgement = judge(concept, found, client)
        tries.append((query, judgement))

        if judgement.enough:
            return (found, tries)
        query = judgement.new_query
    return None, tries


if __name__ == "__main__":
    # 1. 평가셋 개념 30개: 문맥 정밀도 평균, 충분 / 다시 찾음 / 노트 부족 개수, 정답 조각을 관련 있음으로 봤나
    # 2. 노트에 없는 개념("GAN")은 노트 부족, 긴 조각 뒤쪽 개념("멀티헤드 어텐션")은 어떻게 되나
    # 실행: uv run --env-file .env python -m chagok.retrieve [개념 ...]
    #       개념을 주면 그 개념만
    import csv
    import sys

    from kiwipiepy import Kiwi
    from sentence_transformers import CrossEncoder, SentenceTransformer

    from chagok.search import RERANK_MAX_LEN, RERANK_MODEL, is_hit, load_store, rerank, search
    from chagok.store import EMBED_MODEL, ROOT

    # precision은 API 없이 먼저 확인
    yes, no = ChunkJudge(id="a", relevant=True), ChunkJudge(id="b", relevant=False)
    assert Judgment(chunks=[yes, yes, no], enough=True, missing="", new_query="").precision == 2 / 3

    chunks, docs, index = load_store()
    kiwi = Kiwi()
    model = SentenceTransformer(EMBED_MODEL)
    reranker = CrossEncoder(RERANK_MODEL, max_length=RERANK_MAX_LEN)
    client = anthropic.Anthropic()

    def find(query: str) -> list[dict]:
        return rerank(query, search(query, kiwi, model, chunks, docs, index), reranker)

    if sys.argv[1:]:
        concepts = [{"concept": c, "answers": ""} for c in sys.argv[1:]]
    else:
        with open(ROOT / "eval" / "concepts.csv", encoding="utf-8") as f:
            concepts = list(csv.DictReader(f))
        concepts += [{"concept": "GAN", "answers": ""}, {"concept": "멀티헤드 어텐션", "answers": ""}]

    first_precisions = []
    counts = {"충분": 0, "다시 찾음": 0, "노트 부족": 0}
    gold_seen = gold_relevant = 0
    for c in concepts:
        found, tries = retrieve(c["concept"], find, client)
        assert 1 <= len(tries) <= MAX_RETRIES + 1
        first = tries[0][1]
        first_precisions.append(first.precision)
        result = "노트 부족" if found is None else "충분" if len(tries) == 1 else "다시 찾음"
        counts[result] += 1

        # 평가셋 정답 조각이 처음 찾은 조각에 있으면, AI가 그걸 관련 있음으로 봤는지
        answers = [a for a in c["answers"].split(";") if a]
        for j in first.chunks:
            if answers and is_hit(j.id, answers):
                gold_seen += 1
                gold_relevant += j.relevant

        if result != "충분" or first.precision < 1:
            print(f"\n=== {c['concept']} → {result} (정밀도 {first.precision:.2f})")
            for query, j in tries:
                marks = " ".join("O" if ch.relevant else "X" for ch in j.chunks)
                print(f"  검색어 {query!r}: [{marks}] {'충분' if j.enough else '부족: ' + j.missing}")

    n = len(concepts)
    print(f"\n개념 {n}개 · 첫 검색 문맥 정밀도 평균 {sum(first_precisions) / n:.2f}")
    print("  " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    if gold_seen:
        print(f"  정답 조각을 관련 있음으로 봄: {gold_relevant}/{gold_seen}")
    print("OK")

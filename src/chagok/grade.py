"""채점 AI: 내 주말 검토를 흉내 내 "승인할지, 반려라면 어떤 사유일지"를 추정한다.

흐름
    문제 (질문, 모범 답안, 채점 포인트) + 출처 노트 조각 + 같은 개념의 지난 질문
      │ grade            채점 AI → Grade (판정, 확신도, 이유)
      ▼
    approval_rate        여러 문제의 추정 승인율 (북극성 지표 추정)

평가 (__main__)
    load_labeled         내가 판정한 문제: 승인·반려 예시(eval/review_examples.md) + 주말 검토 기록(data/chagok.db)
    agreement            채점 AI 판정과 내 판정이 맞는 비율
                         - 승인/반려 일치 (가장 중요: 승인율 추정이 맞는지)
                         - 반려라면 사유까지 일치

규칙 (기획서 처음 값)
    - 채점 AI 후보는 Claude와 Jev. Claude로 시작하고, 내 판정 50건으로 더 잘 맞는 쪽을 쓴다
    - 채점 AI가 내 판단과 다르면 추정 승인율도 의미가 없다 → 일치율부터
    - 검사 AI(근거·명확함만)와 달리 난이도·중복까지 본다 (내가 실제로 반려하는 이유 전부)
    - 점수가 애매한 문제만 나에게 보낸다 → 확신도를 같이 받는다
    - 평가하는 문제를 예시로 보여주지 않는다 (답을 보고 시험 보는 셈)
"""

import re  # 예시 파일에서 칸 꺼내기
import sqlite3  # 주말 검토 기록
from pathlib import Path  # 예시 파일 경로
from typing import Literal, get_args  # 판정 선택지

import anthropic  # Claude API
from pydantic import BaseModel  # 출력 형식 (판정)

from chagok.generate import MAX_TOKENS, format_chunks

GRADE_MODEL = "claude-haiku-5-5"

# 판정 선택지: 승인 + 반려 사유 (기획서 네 가지 + 내가 실제로 쓴 "너무 어려움", "답안이 장황함")
# Jev의 Choice 질문과 같은 모양 (선택지 하나 + 확신도)
Decision = Literal["승인", "근거 없음", "애매함", "너무 쉬움", "너무 어려움", "답안이 장황함", "중복", "기타"]
DECISIONS = list(get_args(Decision))

# 채점 지시문 초안. 생성·검사 지시문과 따로 둔다
GRADE_SYSTEM = """너는 복습 문제를 주말에 검토하는 사람을 대신해 판정하는 채점자다.
이 사람은 학습 노트로 만든 서술형 문제를 보고, 고치지 않고 그대로 메일로 받아도 될 문제만 승인한다.

판정은 아래 중 하나다. 가장 큰 문제 하나만 고른다.
- 승인: 그대로 써도 된다
- 근거 없음: 모범 답안에 노트에 없는 내용(배경 지식, 연도, 인물, 노트와 다른 주장)이 있다
- 애매함: 질문만 읽고 무엇을 답해야 할지 분명하지 않다. 범위가 정해지지 않았거나("아는 대로"), 노트를 봐야 아는 지칭("모델 2")이 있다
- 너무 쉬움: 정의 한 줄이나 값 하나를 그대로 묻는다. 이유·차이·과정을 설명하게 하지 않는다
- 너무 어려움: 출근길에 머릿속으로 1분 안에 답하기 어렵다. 여러 단계의 계산이나 식 전개, 여러 개념을 한꺼번에 엮어야 답할 수 있다
- 답안이 장황함: 모범 답안이 질문이 묻는 것보다 길거나, 같은 말을 되풀이하거나, 묻지 않은 내용까지 늘어놓아 간결하게 줄여야 한다
- 중복: [같은 개념의 지난 질문] 중 하나와 사실상 같은 것을 묻는다
- 기타: 위에 없는 이유

확신도는 0~1. 판정이 분명하면 높게, 승인과 반려 사이에서 망설여지면 낮게 준다.
이유는 한두 문장으로 쓴다."""


class Grade(BaseModel):
    """채점 결과 하나."""

    decision: Decision
    confidence: float  # 0~1. 낮으면 "애매한 문제" → 나에게 보낼 후보
    reason: str  # 판정 이유 (Jev는 주지 않는 칸. 내 판정과 다를 때 원인 찾기용)


def load_labeled(examples: Path, conn: sqlite3.Connection) -> list[dict]:
    """내가 판정한 문제를 모은다. 출력: [{"concept", "question", "answer", "points", "sources", "label"}, ...]

    1. eval/review_examples.md (20개): "## rNN · 개념" 블록마다
       - 질문, 모범 답안, 채점 포인트(" / "로 나눔), 출처("; "로 나눔. "5. 다층 퍼셉트론"처럼 # 없는 건 앞 출처의 "파일#제목"을 붙임)
       - label: 판정이 승인이면 "승인", 반려면 반려 사유를 DECISIONS로 옮김 (label_of)
    2. data/chagok.db의 questions 표: status가 승인/반려인 것 (주말 검토 기록)
       - points는 " / ", sources는 줄바꿈으로 이어 저장됨
       - label: 승인이면 "승인", 반려면 reason (검토 때 REJECT_REASONS에서 고름)
    """

    def get(block: str, name: str) -> str:
        """'- {name}: 값' 줄의 값. 반려 사유처럼 비어 있으면 콜론 뒤에 공백도 없음 (공백·탭만 건너뜀, 줄은 안 넘어감)"""
        return re.search(rf"^- {name}:[ \t]*(.*)", block, re.M).group(1).strip()

    items = []

    # 1. 승인·반려 예시 (판정 칸이 "승인 / 반려"인 맨 위 안내문은 [1:]로 빠짐)
    for block in re.split(r"^## ", examples.read_text(encoding="utf-8"), flags=re.M)[1:]:
        sources = get(block, "출처").split("; ")
        head = sources[0].split(" > ")[0]  # "파일#제목"
        sources = [src if "#" in src else f"{head} > {src}" for src in sources]
        items.append({
            "concept": block.partition("\n")[0].partition(" · ")[2],
            "question": get(block, "질문"),
            "answer": get(block, "모범 답안"),
            "points": get(block, "채점 포인트").split(" / "),
            "sources": sources,
            "label": label_of(get(block, "판정"), get(block, "반려 사유"), get(block, "근거"), get(block, "명확함")),
        })

    # 2. 주말 검토 기록
    rows = conn.execute(
        "SELECT concept, question, answer, points, sources, status, reason FROM questions "
        "WHERE status IN ('승인', '반려') ORDER BY id"
    ).fetchall()
    for concept, question, answer, points, sources, status, reason in rows:
        items.append({
            "concept": concept,
            "question": question,
            "answer": answer,
            "points": points.split(" / "),
            "sources": [src for src in (sources or "").split("\n") if src],
            "label": label_of(status, reason or ""),
        })

    return items


def label_of(verdict: str, reason: str, grounded: str = "", clear: str = "") -> str:
    """내 판정 → DECISIONS 중 하나.

    - 판정이 "승인"이면 "승인"
    - 반려 사유가 DECISIONS의 이름으로 시작하면 그것 (예: "너무 쉬움 — 난이도를 …" → "너무 쉬움")
    - 아니면 예시의 근거·명확함 칸으로: 근거 탈락 → "근거 없음", 명확함 탈락 → "애매함"
    - 그래도 아니면 "기타" (예: "모범답안 수정 필요")
    """
    if verdict == "승인":
        return "승인"
    for d in DECISIONS:
        if reason.startswith(d):
            return d
    if grounded == "탈락":
        return "근거 없음"
    if clear == "탈락":
        return "애매함"
    return "기타"


def previous_questions(
    conn: sqlite3.Connection, concept: str, question: str
) -> list[str]:
    """같은 개념으로 전에 만든 질문들 (승인·대기·보낸 것). 지금 문제는 뺀다. "중복" 판단용."""
    rows = conn.execute(
        "SELECT question FROM questions "
        "WHERE concept = ? AND question != ? AND status IN ('승인', '대기')",
        (concept, question),
    ).fetchall()
    return [r[0] for r in rows]


def grade(
    item: dict, chunks: list[dict], previous: list[str], client: anthropic.Anthropic
) -> Grade:
    """문제 하나 → 채점 AI → Grade.

    - system=GRADE_SYSTEM
    - user = [노트 조각] format_chunks(chunks) + [같은 개념의 지난 질문] (없으면 "없음")
             + [문제] 개념·질문·모범 답안·채점 포인트
    - output_format=Grade, stop_reason 확인 (generate와 같음)
    - ponytail: Jev와 비교할 때는 이 함수와 같은 모양(Grade를 돌려줌)의 grade_jev를 하나 더 만든다
    """
    user = (
        f"[노트 조각]\n{format_chunks(chunks)}\n\n"
        f"[같은 개념의 지난 질문]\n{chr(10).join(f'- {q}' for q in previous) or '없음'}\n\n"
        f"[문제]\n"
        f"개념: {item['concept']}\n"
        f"질문: {item['question']}\n"
        f"모범 답안: {item['answer']}\n"
        f"채점 포인트: {' / '.join(item['points'])}"
    )
    response = client.messages.parse(
        model=GRADE_MODEL,
        max_tokens=MAX_TOKENS,
        system=GRADE_SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_format=Grade,
    )
    if response.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"{item['concept']}: 채점 실패 ({response.stop_reason})")
    return response.parsed_output


def approval_rate(grades: list[Grade]) -> float:
    """추정 승인율 = 채점 AI가 "승인"이라고 본 비율."""
    return sum(g.decision == "승인" for g in grades) / len(grades)


def agreement(items: list[dict], grades: list[Grade]) -> dict:
    """내 판정(item["label"])과 채점 AI 판정 비교.

    출력: {
        "approve": 승인/반려가 맞은 비율,
        "exact": 판정(사유까지)이 맞은 비율,
        "my_rate": 내 승인율, "ai_rate": 추정 승인율,
        "misses": [(개념, 내 판정, AI 판정, 확신도, 이유), ...],
    }
    """
    pairs = list(zip(items, grades))
    n = len(pairs)

    approve = (
        sum((it["label"] == "승인") == (g.decision == "승인") for it, g in pairs) / n
    )
    exact = sum(it["label"] == g.decision for it, g in pairs) / n
    misses = [
        (it["concept"], it["label"], g.decision, g.confidence, g.reason)
        for it, g in pairs
        if it["label"] != g.decision
    ]

    return {
        "approve": approve,
        "exact": exact,
        "my_rate": sum(it["label"] == "승인" for it, _ in pairs) / n,
        "ai_rate": approval_rate(grades),
        "misses": misses,
    }


if __name__ == "__main__":
    # 내 판정과 일치율 (실행: uv run --env-file .env python -m chagok.grade)
    from chagok.generate import EXAMPLES
    from chagok.graph import open_db
    from chagok.search import is_hit, load_store

    # 1. API 없이: label_of 규칙, approval_rate, agreement 계산
    assert label_of("승인", "") == "승인"
    assert label_of("반려", "너무 쉬움 — 난이도를 …", "통과", "통과") == "너무 쉬움"
    assert label_of("반려", "1969년 … 필요없음", "탈락", "통과") == "근거 없음"
    assert label_of("반려", "모델 2 …", "통과", "탈락") == "애매함"
    assert label_of("반려", "너무 어려움", "통과", "통과") == "너무 어려움"
    assert label_of("반려", "답안이 장황함 — 간결하게 …", "통과", "통과") == "답안이 장황함"
    assert label_of("반려", "모번답안 수정 필요", "통과", "통과") == "기타"
    fake = [Grade(decision=d, confidence=0.8, reason="") for d in ["승인", "근거 없음", "애매함", "너무 쉬움"]]
    labels = [{"concept": c, "label": l} for c, l in zip("abcd", ["승인", "근거 없음", "근거 없음", "승인"])]
    r = agreement(labels, fake)
    assert (r["approve"], r["exact"], r["my_rate"], r["ai_rate"]) == (0.75, 0.5, 0.5, 0.25), r

    # 2. 내가 판정한 문제를 채점 AI에 돌린다
    chunks, _, _ = load_store()
    conn = open_db()
    items = load_labeled(EXAMPLES, conn)
    client = anthropic.Anthropic()
    grades = []
    for it in items:
        found = [ch for ch in chunks if is_hit(ch["id"], it["sources"])]
        assert found, (it["concept"], it["sources"])
        grades.append(grade(it, found, previous_questions(conn, it["concept"], it["question"]), client))

    r = agreement(items, grades)
    n = len(items)
    print(f"내가 판정한 문제 {n}개 (예시 + 주말 검토)")
    print(f"승인/반려 일치 {r['approve']:.2f}  사유까지 일치 {r['exact']:.2f}")
    print(f"내 승인율 {r['my_rate']:.2f}  추정 승인율 {r['ai_rate']:.2f}")
    right = [g.confidence for it, g in zip(items, grades) if it["label"] == g.decision]
    wrong = [g.confidence for it, g in zip(items, grades) if it["label"] != g.decision]
    if right and wrong:
        print(f"확신도 평균: 맞힌 것 {sum(right) / len(right):.2f}, 틀린 것 {sum(wrong) / len(wrong):.2f}")
    for concept, mine, ai, conf, reason in r["misses"]:
        print(f"  {concept}: 나 {mine} / AI {ai} ({conf:.2f}) {reason}")

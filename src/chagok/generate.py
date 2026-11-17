"""문제 생성: 개념 하나와 노트 조각 3개로 복습 문제 하나를 만든다.

흐름
    "기울기 소실" + 리랭크로 남은 조각 3개
      │ load_examples     eval/review_examples.md에서 "승인" 문제만 꺼냄
      │ format_chunks     조각 3개 → 지시문에 넣을 글 (출처 id 포함)
      │ format_examples   승인 문제 → 지시문에 넣을 예시 글 (같은 개념은 뺌)
      │ generate          Claude에 요청 → {질문, 모범 답안, 채점 포인트}
      ▼
    Question

규칙 (기획서 처음 값)
    - 생성 모델: Claude Haiku 5.5
    - 컨텍스트는 적게: 리랭크 후 조각 3개 + 내가 승인한 문제 예시
    - 문제의 근거는 항상 노트 원문(조각)에서 가져온다
    - 채점 포인트 칸은 반드시 채운다 (검사하지 않음 → 출력 형식으로 강제)
"""

import re  # 판정·질문 등 꺼내기, ## 기준 자르기
from pathlib import Path  # 예시 파일 경로

import anthropic  # Claude API
from pydantic import BaseModel  # 출력 형식 (질문·모범 답안·채점 포인트)

from chagok.store import ROOT

MODEL = "claude-haiku-5-5"
MAX_TOKENS = 16000
EXAMPLES = ROOT / "eval" / "review_examples.md"

# 지시문 초안. 반려 사유(근거 없음, 애매함, 너무 쉬움)를 보고 고쳐 나간다
SYSTEM = """너는 학습 노트로 복습 문제를 만드는 출제자다.
주어진 노트 조각만 근거로, 개념 하나에 대한 서술형 문제 하나를 만든다.

- 모범 답안의 모든 문장은 노트 조각에 실제로 있는 내용이어야 한다. 노트에 없는 배경 지식(연도, 인물, 역사 등)은 넣지 않는다.
- 질문은 읽자마자 무엇을 답해야 할지 분명해야 한다.
- 정의 한 줄을 그대로 묻는 문제처럼 너무 쉬운 문제는 피하고, 이유·차이·과정을 설명하게 한다.
- 채점 포인트는 모범 답안에서 꼭 들어가야 할 핵심을 짧게 나눈 것이다.
- 노트 용어는 바꿔 쓰지 않고 그대로 쓴다."""


class Question(BaseModel):
    """만든 문제 하나. 세 칸 모두 반드시 채워짐 (출력 형식으로 강제)."""

    question: str  # 질문
    answer: str  # 모범 답안
    points: list[str]  # 채점 포인트


def load_examples(path: Path) -> list[dict]:
    """review_examples.md에서 판정이 "승인"인 문제만 꺼낸다.

    출력: [{"concept": "퍼셉트론", "question": ..., "answer": ..., "points": [...]}, ...]
      - "## r01 · 퍼셉트론" → concept
      - "- 질문: ..." / "- 모범 답안: ..." / "- 채점 포인트: a / b / c" → " / "로 나눠 리스트
      - "- 판정: 승인"인 것만 (파일 맨 위 안내문의 "승인 / 반려"는 빼야 함)
    """
    text = path.read_text(encoding="utf-8")
    split_text = re.split(r"^## ", text, flags=re.M)[1:]
    examples = []

    for block in split_text:
        verdict = re.search(r"^- 판정: (.+)", block, re.M).group(1).strip()
        if verdict != "승인":
            continue
        concept = block.partition("\n")[0].partition(" · ")[2]
        question = re.search(r"^- 질문: (.+)", block, re.M).group(1).strip()
        answer = re.search(r"^- 모범 답안: (.+)", block, re.M).group(1).strip()
        points = (
            re.search(r"^- 채점 포인트: (.+)", block, re.M)
            .group(1)
            .strip()
            .split(" / ")
        )

        examples.append(
            {
                "concept": concept,
                "question": question,
                "answer": answer,
                "points": points,
            }
        )
    return examples


def format_chunks(chunks: list[dict]) -> str:
    """조각들을 지시문에 넣을 글로 만든다. 조각마다 출처(id)와 본문(text)."""

    parts = []
    for chunk in chunks:
        parts.append(f"출처: {chunk['id']}\n{chunk['text']}")
    return "\n\n".join(parts)


def format_examples(examples: list[dict], concept: str) -> str:
    """승인 문제들을 예시 글로 만든다. 지금 만들 개념과 같은 예시는 뺀다 (베끼지 않게)."""

    parts = []
    for example in examples:
        if example["concept"] == concept:
            continue

        parts.append(
            f"예시 {len(parts)+1} · {example['concept']}\n질문: {example['question']}\n모범 답안: {example['answer']}\n채점 포인트: {' / '.join(example['points'])}"
        )

    return "\n\n".join(parts)


def generate(
    concept: str, chunks: list[dict], examples: list[dict], client: anthropic.Anthropic
) -> Question:
    """개념 + 조각 → Claude → Question.

    - system=SYSTEM, user 메시지 = 개념 + format_examples + format_chunks
    - client.messages.parse(..., output_format=Question) → response.parsed_output
    - stop_reason이 "refusal"이나 "max_tokens"면 에러로 멈춘다
    """
    user = (
        f"[내가 승인한 문제 예시]\n{format_examples(examples, concept)}\n\n"
        f"[노트 조각]\n{format_chunks(chunks)}\n\n"
        f'위 노트 조각만 근거로 "{concept}" 문제를 하나 만들어라.'
    )

    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_format=Question,
    )

    if response.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"{concept}: 생성 실패 ({response.stop_reason})")

    return response.parsed_output


if __name__ == "__main__":
    # 개념 몇 개로 문제를 만들어 본다
    # 실행: uv run --env-file .env python -m chagok.generate [개념 ...]
    #       개념을 안 주면 eval/concepts.csv 앞 3개
    import csv
    import sys

    from kiwipiepy import Kiwi
    from sentence_transformers import CrossEncoder, SentenceTransformer

    from chagok.search import RERANK_MAX_LEN, RERANK_MODEL, load_store, rerank, search
    from chagok.store import EMBED_MODEL

    # 1. 예시: 승인 13개, 같은 개념은 빠지고 채점 포인트는 " / "로 이어짐
    examples = load_examples(EXAMPLES)
    assert len(examples) == 13, len(examples)
    text = format_examples(examples, "퍼셉트론")
    assert "· 퍼셉트론\n" not in text and text.startswith("예시 1 · ")
    assert text.count("예시 ") == 12 and "['" not in text

    if sys.argv[1:]:
        concepts = sys.argv[1:]
    else:
        with open(ROOT / "eval" / "concepts.csv", encoding="utf-8") as f:
            concepts = [row["concept"] for row in csv.DictReader(f)][:3]

    # 2. 검색 → 리랭크로 조각 3개 → 3. 생성
    chunks, docs, index = load_store()
    kiwi = Kiwi()
    model = SentenceTransformer(EMBED_MODEL)
    reranker = CrossEncoder(RERANK_MODEL, max_length=RERANK_MAX_LEN)
    client = anthropic.Anthropic()

    for concept in concepts:
        found = rerank(concept, search(concept, kiwi, model, chunks, docs, index), reranker)
        q = generate(concept, found, examples, client)
        assert q.question and q.answer and q.points and all(q.points), q

        print(f"\n=== {concept}")
        print("조각: " + " | ".join(ch["id"] for ch in found))
        print(f"질문: {q.question}")
        print(f"모범 답안: {q.answer}")
        print(f"채점 포인트: {' / '.join(q.points)}")
    print("\nOK")

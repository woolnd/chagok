"""청킹: 파싱된 노트를 검색용 조각으로 만든다.

흐름
    parse_note() 결과 {file, title, date, pages}
      │ make_header     "퍼셉트론 | 2026-10-15 | 1. 퍼셉트론이란"
      │ make_chunk      머리말 + 본문, 메타데이터 붙이기
      ▼
    [{id, text, file, page, date, topic, kind}, ...]

규칙 (기획서 처음 값)
    - 페이지(## 섹션) 하나 = 조각 하나
    - 조각 맨 앞에 "노트 제목 · 배운 날짜 · 소제목"
    - 메타데이터: 파일명, 페이지 번호(필수), 배운 날짜, 주제, 성격(이론/실습/질문)
    - id: "파일명#제목 > 소제목" (평가셋 정답 표기와 같은 형식 → Recall@k 비교에 사용)
"""

from pathlib import Path

from chagok.parse import parse_note


def make_header(title: str, date: str, heading: str) -> str:
    """조각 맨 앞에 붙일 머리말. 예: "퍼셉트론 | 2026-10-15 | 1. 퍼셉트론이란" """
    # TODO
    return title + " | " + date + " | " + heading


def make_chunk(note: dict, page: dict) -> dict:
    """페이지 하나로 조각 하나를 만든다.

    출력: {
        "id":    "2026-10-15_perceptron.md#퍼셉트론 > 1. 퍼셉트론이란",
        "text":  머리말 + "\\n" + 본문,
        "file":  파일명,
        "page":  페이지 번호,
        "date":  배운 날짜,
        "topic": 주제 (노트 제목),
        "kind":  성격 (이론/실습/질문 — 결정 필요),
    }
    """

    return {
        "id": note["file"] + "#" + note["title"] + " > " + page["heading"],
        "text": make_header(note["title"], note["date"], page["heading"])
        + "\n"
        + page["text"],
        "file": note["file"],
        "page": page["page"],
        "date": note["date"],
        "topic": note["title"],
        "kind": "이론",
    }


def make_chunks(note: dict) -> list[dict]:
    """노트 하나의 모든 페이지를 조각으로 만든다."""

    chunks = []
    for page in note["pages"]:
        chunk = make_chunk(note, page)
        chunks.append(chunk)

    return chunks


if __name__ == "__main__":
    # raw/의 노트를 전부 청킹해서 확인 (실행: uv run python -m chagok.chunk)
    import csv

    root = Path(__file__).parents[2]
    notes = [parse_note(p) for p in sorted((root / "raw").glob("*.md"))]
    chunks = [c for n in notes for c in make_chunks(n)]

    # 페이지 하나 = 조각 하나, id 중복 없음
    pages = sum(len(n["pages"]) for n in notes)
    assert len(chunks) == pages, (len(chunks), pages)
    assert len({c["id"] for c in chunks}) == len(chunks)

    # 퍼셉트론 첫 조각의 id·머리말·메타데이터
    c = next(c for c in chunks if c["file"] == "2026-10-15_perceptron.md")
    assert c["id"] == "2026-10-15_perceptron.md#퍼셉트론 > 1. 퍼셉트론이란", c["id"]
    assert c["text"].startswith("퍼셉트론 | 2026-10-15 | 1. 퍼셉트론이란\n"), c["text"][:40]
    assert (c["page"], c["date"], c["topic"], c["kind"]) == (1, "2026-10-15", "퍼셉트론", "이론")

    # 평가셋 정답마다 그 정답을 담은 조각이 있는지 (정답 = 조각 id 또는 그 아래 ### 소제목)
    ids = [c["id"] for c in chunks]
    with open(root / "eval" / "concepts.csv", encoding="utf-8") as f:
        answers = [a for row in csv.DictReader(f) for a in row["answers"].split(";")]
    missing = [a for a in answers if not any(a == i or a.startswith(i + " > ") for i in ids)]
    assert not missing, missing

    print(f"조각 {len(chunks)}개, 평가셋 정답 {len(answers)}개 모두 조각과 맞물림")
    print("OK")

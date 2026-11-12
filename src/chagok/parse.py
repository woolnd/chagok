"""노트(md) 파서: raw/의 노트 하나를 구조로 바꾼다.

흐름
    raw/2026-10-15_perceptron.md
      │ read_note       파일 읽기
      │ get_date        frontmatter의 "date: 2026-10-15" → "2026-10-15"
      │ get_title       "# 퍼셉트론" → "퍼셉트론"
      │ split_pages     "## " 기준으로 자르기 → [{page, heading, text}, ...]
      ▼
    {file, title, date, pages}

규칙
    - 페이지 = ## 섹션 하나, page는 1부터 순번
    - ## 앞부분(frontmatter, # 제목)은 페이지에 넣지 않는다
    - 표는 이미 마크다운 표이므로 손대지 않는다 (기획서 처음 값)
"""

import re  # 날짜·제목 찾기, ## 기준 자르기
from pathlib import Path  # 파일 경로, 읽기


def read_note(path: Path) -> str:
    """노트 파일 내용을 문자열로 읽는다."""
    return path.read_text(encoding="utf-8")


def get_date(text: str) -> str:
    """frontmatter에서 배운 날짜를 꺼낸다. 예: "2026-10-15" """
    date = re.search(r"^date: (.+)", text, re.M)
    return date.group(1).strip()


def get_title(text: str) -> str:
    """'# ' 로 시작하는 줄에서 노트 제목을 꺼낸다. 예: "퍼셉트론" """
    title = re.search(r"^# (.+)", text, re.M)
    return title.group(1).strip()


def split_pages(text: str) -> list[dict]:
    """'## ' 기준으로 섹션을 나눈다.

    출력: [{"page": 1, "heading": "1. 퍼셉트론이란", "text": "본문..."}, ...]
      - heading: ## 줄의 소제목
      - text: 그 아래 본문 (### 하위 섹션, 표 포함)
    """
    splits = re.split(r"^## ", text, flags=re.M)
    split_pages = []

    for index, page in enumerate(splits[1:], start=1):
        heading, _, body = page.partition("\n")

        split_pages.append({"page": index, "heading": heading, "text": body.strip()})

    return split_pages


def parse_note(path: Path) -> dict:
    """위 함수들을 차례로 불러 노트 하나를 파싱한다.

    출력: {"file": 파일명, "title": 제목, "date": 날짜, "pages": [...]}
    """
    text = read_note(path)
    date = get_date(text)
    title = get_title(text)
    pages = split_pages(text)

    result = {"file": path.name, "title": title, "date": date, "pages": pages}
    return result


if __name__ == "__main__":
    # raw/의 노트를 전부 파싱해서 확인 (실행: uv run python -m chagok.parse)
    raw = Path(__file__).parents[2] / "raw"
    notes = [parse_note(p) for p in sorted(raw.glob("*.md"))]

    # 노트 11개, 페이지 71개
    assert len(notes) == 11, len(notes)
    assert sum(len(n["pages"]) for n in notes) == 71

    # 퍼셉트론 노트의 파일명·제목·날짜·첫 소제목
    p = next(n for n in notes if n["file"] == "2026-10-15_perceptron.md")
    assert p["title"] == "퍼셉트론", p["title"]
    assert p["date"] == "2026-10-15", p["date"]
    assert p["pages"][0]["page"] == 1
    assert p["pages"][0]["heading"] == "1. 퍼셉트론이란", p["pages"][0]["heading"]

    # 논리 게이트 표가 그대로 남아 있는지 (3. 논리 게이트)
    assert "| x₁ | x₂ | y |" in p["pages"][2]["text"]

    # ### 하위 섹션이 본문에 남아 있는지 (2. 가중치 > ### 크기)
    assert "### 크기" in p["pages"][1]["text"]

    for n in notes:
        print(f'{n["file"]}: {n["title"]} ({n["date"]}) 페이지 {len(n["pages"])}개')
    print("OK")

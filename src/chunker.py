"""노트를 검색 단위 청크로 만든다. 섹션 경계로 자르는 건 parser가 한다."""

from pathlib import Path

from parser import NOTES_DIR, parse


def chunk(path: Path) -> list[dict]:
    """노트 하나를 소제목 단위 청크로 만든다."""
    note = parse(path)

    chunks = []

    for section in note["sections"]:
        if not section["text"]:
            continue
        chunks.append({"file": note["file"], "date": note["date"], **section})

    return chunks


def parent_text(file: str, path: list[str]) -> str:
    """부모 섹션과 그 아래 하위 섹션 원문을 소제목과 함께 이어 붙인다."""
    sections = parse(NOTES_DIR / file)["sections"]

    parts = []
    for section in sections:
        if section["path"][: len(path)] != path:
            continue
        heading = "#" * len(section["path"]) + " " + section["path"][-1]
        parts.append(f"{heading}\n{section['text']}".strip())

    return "\n\n".join(parts)

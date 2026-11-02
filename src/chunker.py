"""노트를 검색 단위 청크로 만든다. 섹션 경계로 자르는 건 parser가 한다."""

from pathlib import Path

from parser import parse


def chunk(path: Path) -> list[dict]:
    """노트 하나를 소제목 단위 청크로 만든다."""
    note = parse(path)

    chunks = []

    for section in note["sections"]:
        if not section["text"]:
            continue
        chunks.append({"file": note["file"], "date": note["date"], **section})

    return chunks

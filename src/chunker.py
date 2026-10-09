"""노트를 검색 단위 청크로 만든다. 섹션 경계로 자르는 건 parser가 한다."""

from pathlib import Path

from parser import parse


def chunk(path: Path) -> list[dict]:
    """노트 하나를 소제목 단위 청크로 만든다.

    Args:
        path: 노트 파일 경로.

    Returns:
        청크 리스트. 청크마다 {"file", "date", "path", "text"}.
        서론(h1 ~ 첫 h2)은 parse가 섹션으로 잡지 않아 들어가지 않는다.
    """
    note = parse(path)

    chunks = []

    for section in note["sections"]:
        # h2 바로 밑에 h3가 오면 본문이 비고, 제목은 h3 청크의 path에 이미 있다
        if not section["text"]:
            continue
        chunks.append(
            {"file": note["file"], "date": note["date"], **section}
        )

    return chunks

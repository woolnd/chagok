import datetime

from chunker import chunk


def write_note(tmp_path, body, front="date: 2026-10-08"):
    path = tmp_path / "note.md"
    path.write_text(f"---\n{front}\n---\n{body}", encoding="utf-8")
    return path


def test_chunk_has_file_and_date(tmp_path):
    chunks = chunk(write_note(tmp_path, "# 제목\n## A\n가\n"))
    assert chunks == [
        {
            "file": "note.md",
            "date": datetime.date(2026, 10, 8),
            "path": ["제목", "A"],
            "text": "가",
        }
    ]


def test_empty_section_is_skipped(tmp_path):
    body = "# 제목\n## A\n### B\n나\n"
    paths = [c["path"] for c in chunk(write_note(tmp_path, body))]
    assert paths == [["제목", "A", "B"]]


def test_intro_is_not_chunked(tmp_path):
    body = "# 제목\n서론\n## A\n가\n"
    texts = [c["text"] for c in chunk(write_note(tmp_path, body))]
    assert texts == ["가"]

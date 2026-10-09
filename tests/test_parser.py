import datetime

from format_check import check
from parser import parse


def write_note(tmp_path, body, front="date: 2026-10-08"):
    path = tmp_path / "note.md"
    path.write_text(f"---\n{front}\n---\n{body}", encoding="utf-8")
    return path


def test_date_and_title(tmp_path):
    note = parse(write_note(tmp_path, "# 텍스트 전처리\n"))
    assert note["date"] == datetime.date(2026, 10, 8)
    assert note["title"] == "텍스트 전처리"


def test_section_path_resets_on_new_h2(tmp_path):
    body = "# 전처리\n## 토큰화\n### 형태소 분석\n## 불용어\n"
    paths = [s["path"] for s in parse(write_note(tmp_path, body))["sections"]]
    assert paths == [
        ["전처리", "토큰화"],
        ["전처리", "토큰화", "형태소 분석"],
        ["전처리", "불용어"],
    ]


def test_hash_in_code_block_is_not_heading(tmp_path):
    body = "# 제목\n```python\n# 주석\n## 이것도 주석\n```\n"
    note = parse(write_note(tmp_path, body))
    assert note["heading_count"] == {1: 1}
    assert note["sections"] == []


def test_section_text_stops_at_next_heading(tmp_path):
    body = "# 제목\n## A\n가\n\n```python\n# 주석\n```\n### B\n나\n## C\n다\n"
    texts = [s["text"] for s in parse(write_note(tmp_path, body))["sections"]]
    assert texts == ["가\n\n```python\n# 주석\n```", "나", "다"]


def test_section_text_empty_when_heading_follows(tmp_path):
    body = "# 제목\n## A\n### B\n나\n"
    texts = [s["text"] for s in parse(write_note(tmp_path, body))["sections"]]
    assert texts == ["", "나"]


def test_section_text_keeps_markdown(tmp_path):
    body = "# 제목\n## A\n- 항목\n> 메모: 필기\n"
    assert parse(write_note(tmp_path, body))["sections"][0]["text"] == (
        "- 항목\n> 메모: 필기"
    )


def test_consecutive_memos_are_split(tmp_path):
    body = "# 제목\n## 섹션\n> 메모: 첫째\n> 메모: 둘째\n"
    memos = parse(write_note(tmp_path, body))["memos"]
    assert memos == [
        {"path": ["제목", "섹션"], "text": "첫째"},
        {"path": ["제목", "섹션"], "text": "둘째"},
    ]


def test_memo_word_outside_quote_is_ignored(tmp_path):
    body = "# 제목\n메모: 인용 밖\n\n메모리가 낭비된다\n\n> 그냥 인용\n"
    assert parse(write_note(tmp_path, body))["memos"] == []


def test_memo_before_any_heading(tmp_path):
    memos = parse(write_note(tmp_path, "> 메모: 맨 위\n\n# 제목\n"))["memos"]
    assert memos == [{"path": [], "text": "맨 위"}]


def test_code_without_lang_count(tmp_path):
    body = "# 제목\n```\na\n```\n```python\nb\n```\n```text\nc\n```\n"
    assert parse(write_note(tmp_path, body))["code_without_lang_count"] == 1


def test_check_passes_valid_note(tmp_path):
    body = "# 제목\n## 섹션\n### 소섹션\n```python\nx\n```\n"
    assert check(parse(write_note(tmp_path, body))) == []


def test_check_date(tmp_path):
    cases = {
        "title: 없음": "date 없음",
        "date:": "date 없음",
        'date: "2026-10-08"': "date 형식 오류",
        "date: 10월 8일": "date 형식 오류",
        "date: 2026-10-08 10:00:00": "date 형식 오류",
    }
    for front, expected in cases.items():
        errors = check(parse(write_note(tmp_path, "# 제목\n", front)))
        assert len(errors) == 1 and errors[0].startswith(expected), front


def test_check_headings(tmp_path):
    assert check(parse(write_note(tmp_path, "## 섹션\n"))) == [
        "# 제목 개수 오류: 0개 (1개여야 함)"
    ]
    assert check(parse(write_note(tmp_path, "# 하나\n# 둘\n"))) == [
        "# 제목 개수 오류: 2개 (1개여야 함)"
    ]
    assert check(parse(write_note(tmp_path, "# 제목\n#### 깊음\n##### 더\n"))) == [
        "#### 이하 제목 사용: 2개 (###까지만)"
    ]


def test_check_code_lang(tmp_path):
    body = "# 제목\n```\na\n```\n```\nb\n```\n"
    assert check(parse(write_note(tmp_path, body))) == [
        "코드 블록 언어 표시 없음: 2개 (```python 처럼)"
    ]

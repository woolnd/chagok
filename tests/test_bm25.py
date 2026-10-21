import pytest

import bm25


@pytest.fixture
def notes_dir(tmp_path, monkeypatch):
    # search()는 get_index()를 인자 없이 불러 data/notes를 본다. 임시 폴더를 보게 바꾼다
    notes_dir = tmp_path / "notes"
    get_index = bm25.get_index
    monkeypatch.setattr(bm25, "get_index", lambda: get_index(notes_dir))
    return notes_dir


def write_note(notes_dir, name, body, date="2026-10-08"):
    notes_dir.mkdir(exist_ok=True)
    (notes_dir / name).write_text(f"---\ndate: {date}\n---\n{body}", encoding="utf-8")


def test_tokenize_keeps_content_words_only():
    tokens = bm25.tokenize("초깃값이 크거나 작게 설정하면 어떻게 돼?")
    assert "초깃값" in tokens
    assert "어떻" in tokens  # VA-I(불규칙 활용)도 형용사로 남는다
    assert "이" not in tokens and "?" not in tokens  # 조사·기호는 버린다


def test_search_matches_word_with_josa(notes_dir):
    # 문서가 2개면 BM25 IDF가 0이 되어 점수가 다 같아진다. 3개 이상 둔다
    write_note(notes_dir, "a.md", "# 활성화 함수\n## 시그모이드\n시그모이드를 쓴다\n")
    write_note(notes_dir, "b.md", "# 과일\n## 사과\n사과는 빨갛다\n")
    write_note(notes_dir, "c.md", "# 탈것\n## 기차\n기차는 빠르다\n")

    results = bm25.search("시그모이드는 뭐야?", k=1)

    assert results[0]["path"] == ["활성화 함수", "시그모이드"]


def test_search_returns_retriever_shape(notes_dir):
    write_note(notes_dir, "a.md", "# 과일\n## 사과\n사과 사과 사과\n", date="2026-07-30")
    write_note(notes_dir, "b.md", "# 탈것\n## 기차\n기차 기차\n")
    write_note(notes_dir, "c.md", "# 동물\n## 고양이\n고양이\n")

    results = bm25.search("사과", k=2)

    assert len(results) == 2
    assert set(results[0]) == {"file", "date", "path", "text", "score"}
    assert results[0]["file"] == "a.md"
    assert results[0]["date"] == "2026-07-30"  # retriever처럼 문자열
    assert results[0]["text"] == "사과 사과 사과"
    assert isinstance(results[0]["score"], float)
    assert results[0]["score"] > results[1]["score"]

import numpy as np
import pytest

import retriever


class FakeModel:
    """글자 빈도 벡터. bge-m3(2GB) 대신 써서 테스트를 빠르게 돌린다."""

    def encode(self, texts, normalize_embeddings=True):
        if isinstance(texts, str):
            return self._vector(texts)
        return np.array([self._vector(t) for t in texts])

    def _vector(self, text):
        v = np.zeros(512)
        for ch in text:
            v[ord(ch) % 512] += 1
        return v / np.linalg.norm(v)


@pytest.fixture
def notes_dir(tmp_path, monkeypatch):
    # 실제 색인(data/chroma)을 건드리지 않게 임시 폴더에 저장한다
    monkeypatch.setattr(retriever, "get_model", FakeModel)
    monkeypatch.setattr(retriever, "CHROMA_DIR", tmp_path / "chroma")
    retriever.get_collection.cache_clear()
    yield tmp_path / "notes"
    retriever.get_collection.cache_clear()


def write_note(notes_dir, name, body, date="2026-10-08"):
    notes_dir.mkdir(exist_ok=True)
    (notes_dir / name).write_text(f"---\ndate: {date}\n---\n{body}", encoding="utf-8")


def test_build_index_count(notes_dir):
    write_note(notes_dir, "a.md", "# 과일\n## 사과\n사과 사과\n## 배\n### 품종\n배 배\n")
    write_note(notes_dir, "b.md", "# 탈것\n## 기차\n기차 기차\n")
    assert retriever.build_index(notes_dir) == 3  # 빈 섹션 "배"는 제외
    assert retriever.get_collection().count() == 3


def test_reindex_does_not_duplicate(notes_dir):
    write_note(notes_dir, "a.md", "# 과일\n## 사과\n사과 사과\n")
    retriever.build_index(notes_dir)
    retriever.build_index(notes_dir)
    assert retriever.get_collection().count() == 1


def test_removed_section_is_deleted(notes_dir):
    write_note(notes_dir, "a.md", "# 과일\n## 사과\n사과\n## 포도\n포도\n")
    retriever.build_index(notes_dir)
    write_note(notes_dir, "a.md", "# 과일\n## 사과\n사과\n")
    retriever.build_index(notes_dir)
    assert retriever.get_collection().get()["ids"] == ["a.md#과일 > 사과"]


def test_search_returns_chunks_in_order(notes_dir):
    write_note(notes_dir, "a.md", "# 과일\n## 사과\n사과 사과 사과\n", date="2026-07-30")
    write_note(notes_dir, "b.md", "# 탈것\n## 기차\n기차 기차 기차\n")
    retriever.build_index(notes_dir)

    results = retriever.search("사과", k=2)

    assert [r["file"] for r in results] == ["a.md", "b.md"]
    assert results[0]["path"] == ["과일", "사과"]
    assert results[0]["date"] == "2026-07-30"
    assert results[0]["text"] == "사과 사과 사과"
    assert results[0]["distance"] < results[1]["distance"]

import context


def test_index_text_puts_context_first():
    c = {"path": ["과일", "사과"], "text": "빨간 사과"}
    contexts = {context.chunk_hash(c): "과일 노트에서 사과를 설명한다."}
    assert context.index_text(c, contexts) == "과일 노트에서 사과를 설명한다.\n과일 > 사과\n빨간 사과"
    # 맥락이 없는 섹션(새로 쓴 섹션 등)은 원래 글 그대로 색인한다
    assert context.index_text(c, {}) == "과일 > 사과\n빨간 사과"


def test_contexts_off_by_default(monkeypatch, tmp_path):
    # 꺼져 있으면 파일이 있어도 맥락을 쓰지 않는다. CI는 맥락 없이 돈다
    path = tmp_path / "contexts.json"
    path.write_text('{"a": "맥락"}', encoding="utf-8")
    monkeypatch.setattr(context, "CONTEXT_PATH", path)
    monkeypatch.setattr(context, "USE_CONTEXT", False)
    assert context.get_contexts() == {}
    monkeypatch.setattr(context, "USE_CONTEXT", True)
    assert context.get_contexts() == {"a": "맥락"}

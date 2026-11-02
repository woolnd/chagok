import hybrid


def fake_results(paths):
    # search 결과 형식({"file", "path"})만 흉내 낸다. 앞에 있을수록 등수가 높다
    return lambda query, k: [{"file": "a.md", "path": [p]} for p in paths][:k]


def test_rrf_merges_both_searches(monkeypatch):
    # 임베딩: A, B, C / BM25: B, D → 양쪽에 다 있는 B가 1등, 한쪽에만 있는 D도 올라온다
    monkeypatch.setattr(hybrid.retriever, "search", fake_results(["A", "B", "C"]))
    monkeypatch.setattr(hybrid.bm25, "search", fake_results(["B", "D"]))

    results = hybrid.search("질문", k=4, weight=0.5)

    assert [r["path"] for r in results] == [["B"], ["A"], ["D"], ["C"]]


def test_weight_picks_stronger_side(monkeypatch):
    # 양쪽 1등이 다르면 가중치가 큰 쪽의 1등이 이긴다
    monkeypatch.setattr(hybrid.retriever, "search", fake_results(["A"]))
    monkeypatch.setattr(hybrid.bm25, "search", fake_results(["B"]))

    assert hybrid.search("질문", k=1, weight=0.8)[0]["path"] == ["A"]
    assert hybrid.search("질문", k=1, weight=0.2)[0]["path"] == ["B"]


def fake_embedding(distance):
    # 임베딩 결과는 1등 거리만 있으면 된다. 게이트가 이 값으로 판단한다
    return lambda query, k: [{"file": "a.md", "path": ["A"], "distance": distance}]


def test_gate_blocks_far_query(monkeypatch):
    # 1등도 기준선보다 멀면 노트에 관련 내용이 없다고 보고 빈 결과를 돌려준다
    monkeypatch.setattr(hybrid.retriever, "search", fake_embedding(0.6))
    monkeypatch.setattr(hybrid.bm25, "search", fake_results(["B"]))
    monkeypatch.setattr(hybrid, "THRESHOLD", 0.54)
    assert hybrid.search("질문") == []


def test_gate_passes_near_query_and_is_off_by_default(monkeypatch):
    monkeypatch.setattr(hybrid.retriever, "search", fake_embedding(0.3))
    monkeypatch.setattr(hybrid.bm25, "search", fake_results(["B"]))
    monkeypatch.setattr(hybrid, "THRESHOLD", 0.54)
    assert hybrid.search("질문") != []
    # 기준선을 끄면(None) 아무리 멀어도 막지 않는다
    monkeypatch.setattr(hybrid.retriever, "search", fake_embedding(0.9))
    monkeypatch.setattr(hybrid, "THRESHOLD", None)
    assert hybrid.search("질문") != []

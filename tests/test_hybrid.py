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

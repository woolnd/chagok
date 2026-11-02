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
    return lambda query, k: [{"file": "a.md", "path": ["A"], "distance": distance}]


def test_rerank_gate(monkeypatch):
    # 리랭커 최고점이 기준선보다 낮으면 막고, 높으면 통과. 꺼져 있으면 리랭커를 부르지 않는다
    monkeypatch.setattr(hybrid.retriever, "search", fake_embedding(0.3))
    monkeypatch.setattr(hybrid.bm25, "search", fake_results(["B"]))
    monkeypatch.setattr(hybrid, "RERANK_THRESHOLD", -9.6)

    monkeypatch.setattr(hybrid.reranker, "max_score", lambda query, chunks: -11.0)
    assert hybrid.search("질문") == []
    monkeypatch.setattr(hybrid.reranker, "max_score", lambda query, chunks: 2.0)
    assert hybrid.search("질문") != []

    def fail(query, chunks):
        raise AssertionError("기준선이 꺼져 있으면 리랭커(2GB)를 불러오면 안 된다")

    monkeypatch.setattr(hybrid.reranker, "max_score", fail)
    monkeypatch.setattr(hybrid, "RERANK_THRESHOLD", None)
    assert hybrid.search("질문") != []

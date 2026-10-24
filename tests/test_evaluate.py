import pytest

import evaluate


def write_csv(tmp_path, lines):
    path = tmp_path / "retrieval.csv"
    path.write_text("id,query,type,answers,memo\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return path


class FakeCollection:
    """색인 대신 id 목록만 돌려준다. bge-m3와 실제 색인 없이 확인하려고."""

    def __init__(self, ids):
        self.ids = ids

    def get(self, include):
        return {"ids": self.ids}


def fake_search(paths):
    # search 결과 형식({"file", "path"})만 흉내 낸다
    return lambda query, k: [{"file": "a.md", "path": p} for p in paths][:k]


def test_load_eval_splits_answers(tmp_path):
    path = write_csv(
        tmp_path,
        [
            "q1,질문,비교,a.md#A > B;a.md#A > C,",
            "q2,질문,답없음,,",
        ],
    )
    rows = evaluate.load_eval(path)
    assert rows[0]["answers"] == ["a.md#A > B", "a.md#A > C"]
    assert rows[1]["answers"] == []  # [""]가 아님


def test_load_eval_reads_set(tmp_path):
    # set 열을 못 읽으면 회귀/능력 묶음이 비어 CI가 판정을 못 한다
    path = tmp_path / "retrieval.csv"
    path.write_text(
        "id,query,type,answers,memo,set\nq1,질문,문장,a.md#A,,회귀\nq2,질문,답없음,,,능력\n",
        encoding="utf-8",
    )
    rows = evaluate.load_eval(path)
    assert [r["set"] for r in rows] == ["회귀", "능력"]


def test_check_indexed_passes(monkeypatch):
    monkeypatch.setattr(evaluate, "get_collection", lambda: FakeCollection(["a.md#A > B"]))
    evaluate.check_indexed([{"id": "q1", "answers": ["a.md#A > B"]}, {"id": "q2", "answers": []}])


def test_check_indexed_stops_on_missing(monkeypatch, capsys):
    monkeypatch.setattr(evaluate, "get_collection", lambda: FakeCollection(["a.md#A > B"]))
    with pytest.raises(SystemExit) as exc:
        evaluate.check_indexed([{"id": "q1", "answers": ["a.md#A > B", "a.md#A > X"]}])
    assert exc.value.code != 0  # 실패 코드로 끝나야 한다
    assert "q1: a.md#A > X" in capsys.readouterr().out


def test_find_rank(monkeypatch):
    monkeypatch.setattr(evaluate, "search", fake_search([["A", "X"], ["A", "B"], ["A", "C"]]))
    row = {"query": "질문", "answers": ["a.md#A > B", "a.md#A > C"]}
    assert evaluate.find_rank(row) == 2  # 정답 중 처음 나온 등수


def test_find_rank_miss(monkeypatch):
    monkeypatch.setattr(evaluate, "search", fake_search([["A", "X"], ["A", "Y"]]))
    assert evaluate.find_rank({"query": "질문", "answers": ["a.md#A > B"]}) is None


def test_summarize():
    s = evaluate.summarize([1, 3, None])
    assert s["n"] == 3
    assert s["hit5"] == pytest.approx(2 / 3)
    assert s["hit1"] == pytest.approx(1 / 3)
    assert s["mrr"] == pytest.approx((1 + 1 / 3) / 3)

import agreement
import generate


def test_docs_from_sources_rebuilds_parent_text(monkeypatch):
    monkeypatch.setattr(agreement, "parent_text", lambda file, path: f"{file}|{'/'.join(path)}")
    docs = agreement.docs_from_sources(["a.md#제목 > A"])
    assert docs == [{"source": "a.md#제목 > A", "text": "a.md|제목/A"}]


def test_compare_lines_up_human_and_evaluator():
    judgment = {"verdict": "통과", "reason": "r"}
    evaluation = generate.Evaluation(**{item: judgment for item in generate.ITEMS}, feedback="")
    label = {item: "통과" for item in generate.ITEMS} | {"clarity": "미달", "verdict": "미달"}
    rows = agreement.compare(label, evaluation)
    assert rows["clarity"] == ("미달", "통과") and rows["verdict"] == ("미달", "통과")
    assert rows["answer_quote"] == ("통과", "통과")

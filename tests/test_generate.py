import json
import types

import generate

DOCS = [{"source": "a.md#A", "text": "풀링은 공간을 줄이는 연산이다. 매개변수가 없다."}]
OK = generate.Generated(
    quotes=["풀링은 공간을 줄이는 연산이다."], question="Q", answer="A", follow_up="F", insufficient=False
)
BAD = OK.model_copy(update={"quotes": ["풀링은 공간을 줄인다."]})


def fake_response(stop_reason="end_turn"):
    # API 응답에서 기록에 쓰는 칸만 흉내 낸다
    usage = types.SimpleNamespace(
        input_tokens=100, output_tokens=10, cache_creation_input_tokens=5, cache_read_input_tokens=None
    )
    return types.SimpleNamespace(stop_reason=stop_reason, usage=usage)


def test_check_passes_verbatim_quote():
    assert generate.check(OK, DOCS) == []


def test_check_catches_changed_quote_and_empty_fields():
    assert generate.check(BAD, DOCS) == ["원문에 없는 인용: 풀링은 공간을 줄인다."]
    empty = OK.model_copy(update={"quotes": [], "follow_up": " "})
    assert generate.check(empty, DOCS) == ["빈 칸: follow_up", "인용 없음"]


def test_check_passes_insufficient():
    # 근거 부족은 실패가 아니라 정상 결과다
    insufficient = generate.Generated(quotes=[], question="", answer="", follow_up="", insufficient=True)
    assert generate.check(insufficient, DOCS) == []


def test_run_retries_once(monkeypatch):
    # 1회차가 게이트 2에 걸리면 한 번만 다시 만든다
    results = iter([BAD, OK])
    monkeypatch.setattr(generate, "generate", lambda client, k, d, f="": (next(results), fake_response()))
    result, errors, responses = generate.run(None, "풀링", DOCS)
    assert (result, errors, len(responses)) == (OK, [], 2)

    monkeypatch.setattr(generate, "generate", lambda client, k, d, f="": (BAD, fake_response()))
    result, errors, responses = generate.run(None, "풀링", DOCS)
    assert errors and len(responses) == 2


def test_run_counts_refusal_as_failure(monkeypatch):
    monkeypatch.setattr(generate, "generate", lambda client, k, d, f="": (None, fake_response("refusal")))
    result, errors, responses = generate.run(None, "풀링", DOCS)
    assert (result, errors, len(responses)) == (None, ["거절됨"], 2)


def test_log_run_appends_line_with_summed_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(generate, "RUNS_PATH", tmp_path / "runs" / "generate.jsonl")
    ok = {"status": "검토 대기", "result": OK, "gate2": [], "evaluations": [], "revised": False, "responses": [fake_response(), fake_response()]}
    refused = {"status": "게이트 2 실패", "result": None, "gate2": ["거절됨"], "evaluations": [], "revised": False, "responses": [fake_response("refusal")]}
    generate.log_run("풀링", DOCS, ok, 1.23)
    generate.log_run("풀링", DOCS, refused, 1.0)

    lines = [json.loads(line) for line in generate.RUNS_PATH.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert lines[0]["tokens"] == {"input": 200, "output": 20, "cache_write": 10, "cache_read": 0}
    assert lines[0]["result"]["question"] == "Q" and lines[0]["prompt_version"] == generate.PROMPT_VERSION
    assert lines[1]["result"] is None and lines[1]["gate2"] == ["거절됨"]

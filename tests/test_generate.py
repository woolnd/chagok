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


def test_check_catches_note_word_and_filled_insufficient():
    # 받는 사람은 노트를 보지 않는다. 근거 부족인데 칸이 채워져 있으면 섞인 결과다
    assert generate.check(OK.model_copy(update={"follow_up": "노트에 나온 특징은?"}), DOCS) == ["'노트'라는 말: follow_up"]
    mixed = OK.model_copy(update={"insufficient": True})
    assert generate.check(mixed, DOCS) == ["근거 부족인데 칸이 채워짐"]


def evaluation(verdict, feedback="두 가지로 줄여라"):
    judgment = {"verdict": verdict, "reason": "r"}
    return generate.Evaluation(**{item: judgment for item in generate.ITEMS}, feedback=feedback)


def test_evaluation_verdict_order():
    # 미달이 하나라도 있으면 미달, 그다음 판단 불가, 아니면 통과
    mixed = evaluation("통과").model_copy(update={"clarity": generate.Judgment(verdict="판단 불가", reason="r")})
    assert mixed.verdict() == "판단 불가"
    mixed = mixed.model_copy(update={"difficulty": generate.Judgment(verdict="미달", reason="r")})
    assert mixed.verdict() == "미달"
    assert evaluation("통과").verdict() == "통과"


def produce_with(monkeypatch, generated, evaluations):
    # 생성·평가 결과를 순서대로 돌려주고, 생성 때 붙은 피드백을 모은다
    generated, evaluations, feedbacks = iter(generated), iter(evaluations), []

    def fake_generate(client, k, d, f=""):
        feedbacks.append(f)
        return next(generated), fake_response()

    monkeypatch.setattr(generate, "generate", fake_generate)
    monkeypatch.setattr(generate, "evaluate", lambda client, d, r: (next(evaluations), fake_response()))
    return generate.produce(None, "풀링", DOCS), feedbacks


def test_produce_pass_goes_to_review(monkeypatch):
    outcome, feedbacks = produce_with(monkeypatch, [OK], [evaluation("통과")])
    assert (outcome["status"], len(outcome["responses"]), outcome["revised"]) == ("검토 대기", 2, False)


def test_produce_regenerates_once_with_feedback(monkeypatch):
    outcome, feedbacks = produce_with(monkeypatch, [OK, OK], [evaluation("미달"), evaluation("통과")])
    assert (outcome["status"], len(outcome["responses"]), outcome["revised"]) == ("검토 대기", 4, True)
    assert feedbacks[0] == "" and "두 가지로 줄여라" in feedbacks[1]

    outcome, _ = produce_with(monkeypatch, [OK, OK], [evaluation("미달"), evaluation("미달")])
    assert outcome["status"] == "탈락"


def test_produce_stops_without_evaluation(monkeypatch):
    # 근거 부족·게이트 2 실패는 평가자를 부르지 않고, 판단 불가는 재생성하지 않는다
    insufficient = generate.Generated(quotes=[], question="", answer="", follow_up="", insufficient=True)
    assert produce_with(monkeypatch, [insufficient], [])[0]["status"] == "근거 부족"
    assert produce_with(monkeypatch, [BAD, BAD], [])[0]["status"] == "게이트 2 실패"
    assert produce_with(monkeypatch, [OK], [evaluation("판단 불가")])[0]["status"] == "판단 불가"


def test_produce_stops_at_call_budget(monkeypatch):
    # 게이트 2 재시도가 겹쳐 호출이 MAX_CALLS에 닿으면 평가 전에 멈춘다
    outcome, _ = produce_with(monkeypatch, [BAD, OK, BAD, OK], [evaluation("미달")])
    assert (outcome["status"], len(outcome["responses"])) == ("판단 불가", generate.MAX_CALLS)

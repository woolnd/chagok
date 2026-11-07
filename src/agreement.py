"""사람 판정이 있는 문제를 평가자에게 채점시켜 평가자-사람 일치율을 잰다. 로컬 전용."""

import csv
import json
import time
from datetime import datetime
from pathlib import Path

import anthropic

import generate
from chunker import parent_text
from retriever import PATH_SEP

LABELS_PATH = Path("eval/generation_labels.csv")
OUT_PATH = Path("data/runs/agreement.jsonl")


def docs_from_sources(sources: list[str]) -> list[dict]:
    """실행 기록의 출처 경로로 노트 원문을 다시 꺼낸다."""
    docs = []
    for source in sources:
        file, path = source.split("#", 1)
        docs.append({"source": source, "text": parent_text(file, path.split(PATH_SEP))})
    return docs


def load_cases() -> list[tuple[dict, dict]]:
    """사람 판정과 그 문제를 만든 실행 기록을 짝지어 읽는다."""
    with open(generate.RUNS_PATH, encoding="utf-8") as f:
        runs = {(r["date"], r["keyword"]): r for r in map(json.loads, f)}
    with open(LABELS_PATH, encoding="utf-8") as f:
        return [(label, runs[(label["run_date"], label["keyword"])]) for label in csv.DictReader(f)]


def compare(label: dict, evaluation: generate.Evaluation) -> dict:
    """항목별·최종 판정을 사람과 평가자로 나란히 놓는다."""
    rows = {item: (label[item], getattr(evaluation, item).verdict) for item in generate.ITEMS}
    rows["verdict"] = (label["verdict"], evaluation.verdict())
    return rows


if __name__ == "__main__":
    client = anthropic.Anthropic()
    results = []
    for label, run in load_cases():
        docs = docs_from_sources(run["sources"])
        start = time.perf_counter()
        evaluation, response = generate.evaluate(client, docs, generate.Generated(**run["result"]))
        seconds = time.perf_counter() - start
        if evaluation is None:
            print(f"{label['keyword']}: 거절됨")
            continue

        rows = compare(label, evaluation)
        results.append(rows)
        record = {
            "date": datetime.now().isoformat(timespec="seconds"),
            "keyword": label["keyword"],
            "run_date": label["run_date"],
            "model": generate.MODEL,
            "prompt_version": generate.PROMPT_VERSION,
            "human": {k: h for k, (h, _) in rows.items()},
            "evaluation": evaluation.model_dump(),
            "tokens": {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
                "cache_write": response.usage.cache_creation_input_tokens or 0,
                "cache_read": response.usage.cache_read_input_tokens or 0,
            },
            "seconds": round(seconds, 1),
        }
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        marks = " ".join(f"{h}/{e}{'' if h == e else '❌'}" for h, e in rows.values())
        print(f"{label['keyword']}: {marks} | {record['seconds']}초")
        if evaluation.feedback:
            print(f"  피드백: {evaluation.feedback}")

    n = len(results)
    print(f"\n사람/평가자 순서: {', '.join(generate.ITEMS)}, 최종")
    for key in (*generate.ITEMS, "verdict"):
        same = sum(r[key][0] == r[key][1] for r in results)
        print(f"{key:18} 일치 {same}/{n}")
    caught = [r for r in results if r["verdict"][0] == "미달"]
    print(f"사람 미달 {len(caught)}개 중 평가자도 미달 {sum(r['verdict'][1] == '미달' for r in caught)}개")

import csv
import sys
from pathlib import Path

from retriever import PATH_SEP, get_collection, search

EVAL_PATH = Path("eval/retrieval.csv")
K = 5
REGRESSION_TARGET = 1.0


def load_eval(path: Path = EVAL_PATH) -> list[dict]:
    """평가셋 csv를 읽는다."""
    with open(path, "r", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    for row in rows:
        row["answers"] = row["answers"].split(";") if row["answers"] else []

    return rows


def check_indexed(rows: list[dict]) -> None:
    """정답 경로가 모두 색인에 있는지 확인하고, 없으면 멈춘다."""
    indexed = set(get_collection().get(include=[])["ids"])

    missing = []
    for row in rows:
        for answer in row["answers"]:
            if answer not in indexed:
                missing.append((row["id"], answer))

    if missing:
        for qid, answer in missing:
            print(f"{qid}: {answer}")
        raise SystemExit("색인에 없는 정답이 있다. build_index()를 다시 돌려라")


def find_rank(row: dict) -> int | None:
    """질문 하나를 검색해 정답이 처음 나온 등수를 찾는다."""
    chunks = search(row["query"], K)

    for rank, chunk in enumerate(chunks, start=1):
        key = f"{chunk['file']}#{PATH_SEP.join(chunk['path'])}"
        if key in row["answers"]:
            return rank

    return None


def summarize(ranks: list[int | None]) -> dict:
    """등수 목록으로 Hit@5, Hit@1, MRR을 계산한다."""
    n = len(ranks)
    hit5 = sum(r is not None for r in ranks) / n
    hit1 = sum(r == 1 for r in ranks) / n
    mrr = sum(1 / r for r in ranks if r is not None) / n

    return {"n": n, "hit5": hit5, "hit1": hit1, "mrr": mrr}


if __name__ == "__main__":
    args = sys.argv[1:]
    use_bm25 = "bm25" in args
    if use_bm25:
        from bm25 import search
    elif "embedding" not in args:
        import hybrid

        i = args.index("hybrid") + 1 if "hybrid" in args else len(args)
        weight = float(args[i]) if i < len(args) else hybrid.WEIGHT
        search = lambda query, k: hybrid.search(query, k, weight)  # noqa: E731
        print(f"하이브리드 임베딩 : BM25 = {weight} : {1 - weight:.1f}")
        if "threshold" in args:
            hybrid.THRESHOLD = float(args[args.index("threshold") + 1])
        if "rerank" in args:
            hybrid.RERANK_THRESHOLD = float(args[args.index("rerank") + 1])
        print(f"관련도 기준선 거리 {hybrid.THRESHOLD} / 리랭커 {hybrid.RERANK_THRESHOLD}\n")

    rows = load_eval()
    check_indexed(rows)

    scored = [row for row in rows if row["type"] != "답없음"]

    for row in scored:
        row["rank"] = find_rank(row)

    groups = {
        "전체": scored,
        "회귀": [r for r in scored if r["set"] == "회귀"],
        "능력": [r for r in scored if r["set"] == "능력"],
        "메인(키워드)": [r for r in scored if r["type"] == "키워드"],
        "보조": [r for r in scored if r["type"] != "키워드"],
    }
    for qtype in ("문장", "비교", "한영혼용"):
        groups[f"  {qtype}"] = [r for r in scored if r["type"] == qtype]

    print(f"{'':14}{'개수':>4}{'Hit@5':>8}{'Hit@1':>8}{'MRR':>7}")
    for name, group in groups.items():
        if not group:
            continue
        s = summarize([r["rank"] for r in group])
        print(f"{name:14}{s['n']:>4}{s['hit5']:>8.0%}{s['hit1']:>8.0%}{s['mrr']:>7.2f}")

    print("\n틀린 질문")
    for row in scored:
        if row["rank"] is None:
            print(f"{row['id']} [{row['type']}] {row['query']}")
            for i, chunk in enumerate(search(row["query"], K), start=1):
                print(f"  {i}. {chunk['file']}#{PATH_SEP.join(chunk['path'])}")

    no_answer = [row for row in rows if row["type"] == "답없음"]
    blocked = [row for row in no_answer if not search(row["query"], K)]
    print(f"\n답없음 {len(no_answer)}개 중 결과 없음 {len(blocked)}개")
    for row in no_answer:
        print(f"  {'✅' if row in blocked else '❌'} {row['id']} {row['query']}")

    regression = summarize([r["rank"] for r in groups["회귀"]])
    if not use_bm25 and regression["hit5"] < REGRESSION_TARGET:
        raise SystemExit(f"\n회귀 Hit@5 {regression['hit5']:.0%} < 목표 {REGRESSION_TARGET:.0%}")

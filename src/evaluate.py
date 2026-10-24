import csv
import sys
from pathlib import Path

from retriever import PATH_SEP, get_collection, search

EVAL_PATH = Path("eval/retrieval.csv")  # 프로젝트 루트 기준
K = 5


def load_eval(path: Path = EVAL_PATH) -> list[dict]:
    """평가셋 csv를 읽는다.

    Args:
        path: 평가셋 csv 경로.

    Returns:
        질문마다 {"id", "query", "type", "answers", "memo"}.
        answers는 "파일#소제목 > 경로" 리스트이고, 답없음은 빈 리스트다.
    """
    with open(path, "r", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    for row in rows:
        # 정답이 여러 개면 한 칸에 ";"로 이어져 있다. 빈칸은 [""]가 되지 않게 따로 처리
        row["answers"] = row["answers"].split(";") if row["answers"] else []

    return rows


def check_indexed(rows: list[dict]) -> None:
    """정답 경로가 모두 색인에 있는지 확인하고, 없으면 멈춘다.

    Args:
        rows: load_eval 결과.

    Raises:
        SystemExit: 색인에 없는 정답이 하나라도 있을 때.
    """
    # 색인 id는 "파일#소제목 > 경로"라 answers와 그대로 비교된다
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
    """질문 하나를 검색해 정답이 처음 나온 등수를 찾는다.

    Args:
        row: 평가셋 한 행.

    Returns:
        1부터 K까지의 등수. 상위 K개 안에 정답이 없으면 None.
    """
    chunks = search(row["query"], K)  # search(질문, K)

    for rank, chunk in enumerate(chunks, start=1):
        key = f"{chunk['file']}#{PATH_SEP.join(chunk['path'])}"
        if key in row["answers"]:
            return rank

    return None


def summarize(ranks: list[int | None]) -> dict:
    """등수 목록으로 Hit@5, Hit@1, MRR을 계산한다.

    Args:
        ranks: 질문마다 find_rank 결과.

    Returns:
        {"n", "hit5", "hit1", "mrr"}. hit5·hit1은 0~1 비율.
    """
    n = len(ranks)
    hit5 = sum(r is not None for r in ranks) / n
    hit1 = sum(r == 1 for r in ranks) / n
    mrr = sum(1 / r for r in ranks if r is not None) / n

    return {"n": n, "hit5": hit5, "hit1": hit1, "mrr": mrr}


if __name__ == "__main__":
    # python src/evaluate.py bm25 → BM25로 채점. 정답 경로는 같은 노트에서 나와 Chroma로 검사해도 된다
    if sys.argv[1:] == ["bm25"]:
        from bm25 import search

    rows = load_eval()
    check_indexed(rows)

    # 답없음은 맞힐 정답이 없어 지금은 채점하지 않는다
    scored = [row for row in rows if row["type"] != "답없음"]

    for row in scored:
        row["rank"] = find_rank(row)

    # 회귀는 Hit@5가 떨어지지 않는지, 능력은 MRR이 오르는지 본다
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

    # 틀린 질문은 상위 K개를 같이 보여준다. 빠뜨린 정답인지 검색 실패인지 사람이 판단
    print("\n틀린 질문")
    for row in scored:
        if row["rank"] is None:
            print(f"{row['id']} [{row['type']}] {row['query']}")
            for i, chunk in enumerate(search(row["query"], K), start=1):
                print(f"  {i}. {chunk['file']}#{PATH_SEP.join(chunk['path'])}")

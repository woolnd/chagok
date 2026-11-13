"""검색: 개념 하나로 노트 조각을 찾아온다.

흐름
    "기울기 소실"
      ├─ search_bm25     kiwi 단어로 BM25 점수 → 상위 TOP_K 번호
      ├─ search_vector   bge-m3 벡터로 FAISS HNSW → 상위 TOP_K 번호
      ▼
    rrf                  두 순위를 등수로 합치기 → 상위 TOP_K 번호
      ▼
    chunks[번호]         조각 원본으로 바꿔 돌려줌        ← search()
      ▼
    rerank               리랭커로 다시 정렬 → RERANK_KEEP개만 남김

규칙 (기획서 처음 값)
    - top-k 10
    - BM25(kiwi 형태소) + 벡터, RRF로 합침
    - HNSW ef_search 64 (적재 때 인덱스에 저장됨)
    - 리랭커 bge-reranker-v2-m3, 3개 남김 (4개 비교 후 결정)

평가 (__main__)
    - eval/concepts.csv 개념 30개로 Recall@1·3·5·10, MRR (RRF 10개, 리랭크 후 3개)
    - 정답 판정: 조각 id == 정답, 또는 정답이 "조각 id > ..."로 시작 (### 정답은 위 ## 조각이 맞힘)
    - HNSW 결과와 전부 비교(IndexFlatIP) 결과가 겹치는 비율
"""

import csv  # 평가셋 읽기
import json  # store/ 조각·단어 목록 읽기
import math  # BM25의 log
from collections import Counter  # 조각 안 단어 개수 세기

import faiss  # 벡터 검색
from kiwipiepy import Kiwi  # 검색어 형태소 분석
from sentence_transformers import CrossEncoder, SentenceTransformer  # 리랭커, 검색어 벡터화

from chagok.store import EMBED_MODEL, ROOT, STORE, tokenize

TOP_K = 10
RRF_K = 60  # RRF 점수 = 1 / (RRF_K + 등수)

RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
RERANK_KEEP = 3
RERANK_MAX_LEN = 1024  # 검색어 + 조각 토큰 수 상한 (비교할 때 쓴 값)

# BM25 기본값 (보통 쓰는 값)
BM25_K1 = 1.5  # 같은 단어가 여러 번 나올 때 점수가 얼마나 더 오를지
BM25_B = 0.75  # 긴 조각의 점수를 얼마나 깎을지


def load_store() -> tuple[list[dict], list[list[str]], faiss.Index]:
    """store/의 세 파일을 읽는다. 세 개 모두 i번째 = i번째 조각."""
    chunks = json.loads((STORE / "chunks.json").read_text(encoding="utf-8"))
    tokens = json.loads((STORE / "bm25_tokens.json").read_text(encoding="utf-8"))
    index = faiss.read_index(str(STORE / "faiss.index"))

    return chunks, tokens, index


def bm25_scores(query: list[str], docs: list[list[str]]) -> list[float]:
    """검색어 단어 목록으로 조각마다 BM25 점수를 매긴다. (i번째 점수 = i번째 조각)

    조각 d, 검색어 단어 q마다 더한다:
        idf(q) * tf * (K1 + 1) / (tf + K1 * (1 - B + B * len(d) / 평균 조각 길이))
        tf      = 조각 d 안에 q가 나온 횟수
        idf(q)  = log((N - n + 0.5) / (n + 0.5) + 1)
        N = 조각 수, n = q가 들어 있는 조각 수

    점수 = 드문가(idf) × 많이 나오나(tf) × 조각이 길어서 유리한가(길이 보정)
        - idf: 드문 단어일수록 큼. "소실"(3개 조각) ≈ 3.1, "기울기"(20개 조각) ≈ 1.3
               log는 차이를 눌러주고, +0.5는 0으로 나누기 방지, +1은 음수 방지
        - tf:  많이 나올수록 오르지만 점점 덜 오름 (최대 K1 + 1).
               K1 = 1.5일 때 tf 1 → 1.0, 2 → 1.43, 5 → 1.92, 100 → 2.46
               → 같은 단어를 도배한 조각이 무조건 이기지 않게
        - 길이: 긴 조각은 아무 단어나 나올 확률이 높으니 평균보다 길면 깎고 짧으면 올림.
               B는 길이를 얼마나 반영할지 (0이면 무시, 1이면 전부)

    Elasticsearch·Lucene 기본 점수 방식. K1 1.2~2.0, B 0.75가 흔한 값
    """
    N = len(docs)
    avg_len = sum(len(d) for d in docs) / N
    n = Counter(w for d in docs for w in set(d))

    scores = []

    for d in docs:
        tf = Counter(d)
        score = 0
        for q in query:
            if q not in tf:
                continue
            idf = math.log((N - n[q] + 0.5) / (n[q] + 0.5) + 1)
            score += (
                idf
                * tf[q]
                * (BM25_K1 + 1)
                / (tf[q] + BM25_K1 * (1 - BM25_B + BM25_B * len(d) / avg_len))
            )
        scores.append(score)

    return scores


def search_bm25(query: str, kiwi: Kiwi, docs: list[list[str]], k: int) -> list[int]:
    """검색어(개념)를 kiwi로 자르고 BM25 점수 상위 k개 조각 번호를 돌려준다."""
    tokens = tokenize(kiwi, query)
    scores = bm25_scores(tokens, docs)
    top_k = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

    return top_k


def search_vector(
    query: str, model: SentenceTransformer, index: faiss.Index, k: int
) -> list[int]:
    """검색어(개념)를 bge-m3 벡터로 바꿔 가까운 조각 번호 k개를 돌려준다."""
    vector = model.encode([query], normalize_embeddings=True)
    _, ids = index.search(vector, k)

    return ids[0].tolist()


def rrf(rankings: list[list[int]], k: int) -> list[int]:
    """여러 순위를 등수로 합친다. 조각마다 1 / (RRF_K + 등수)를 더해 높은 순으로 k개.

    예: BM25 [3, 7, 1], 벡터 [7, 3, 9]
        → 3, 7은 양쪽에 있어 위로 → [3, 7, 1, 9] 근처
    등수는 1부터.
    """
    scores = {}  # 조각 번호 → RRF 점수

    for ranking in rankings:
        for rank, i in enumerate(ranking, start=1):
            scores[i] = scores.get(i, 0) + 1 / (RRF_K + rank)

    return sorted(scores, key=lambda i: scores[i], reverse=True)[:k]


def search(
    query: str,
    kiwi: Kiwi,
    model: SentenceTransformer,
    chunks: list[dict],
    docs: list[list[str]],
    index: faiss.Index,
    k: int = TOP_K,
) -> list[dict]:
    """BM25 + 벡터 → RRF → 상위 k개 조각 원본."""
    bm25_ids = search_bm25(query, kiwi, docs, k)
    vector_ids = search_vector(query, model, index, k)
    ids = rrf([bm25_ids, vector_ids], k)

    return [chunks[i] for i in ids]


def rerank(query: str, found: list[dict], reranker: CrossEncoder, keep: int = RERANK_KEEP) -> list[dict]:
    """리랭커가 (검색어, 조각)을 한 쌍씩 직접 읽고 점수를 매겨 다시 정렬, 상위 keep개만 남긴다.

    BM25·벡터는 검색어와 조각을 따로 보고 비교하지만, 리랭커는 둘을 같이 읽어서 더 정확하다.
    대신 느려서 RRF로 줄인 10개에만 쓴다.
    """
    scores = reranker.predict([(query, chunk["text"]) for chunk in found])
    order = sorted(range(len(found)), key=lambda i: scores[i], reverse=True)[:keep]

    return [found[i] for i in order]


def is_hit(chunk_id: str, answers: list[str]) -> bool:
    """조각이 정답인지. 정답과 같거나, 정답이 이 조각 아래 ### 소제목이면 맞힘."""
    return any(a == chunk_id or a.startswith(chunk_id + " > ") for a in answers)


def first_hit_rank(ids: list[str], answers: list[str]) -> int | None:
    """검색 결과 id 목록에서 처음 맞힌 등수(1부터). 못 맞히면 None."""
    for rank, chunk_id in enumerate(ids, start=1):
        if is_hit(chunk_id, answers):
            return rank
    return None


if __name__ == "__main__":
    # 평가 (실행: uv run python -m chagok.search)
    assert is_hit("a.md#제목 > 1. 소제목", ["a.md#제목 > 1. 소제목 > 세부"])
    assert not is_hit("a.md#제목 > 1. 소제목", ["a.md#제목 > 10. 다른 소제목"])
    assert rrf([[3, 7, 1], [7, 3, 9]], 10) == [3, 7, 1, 9]

    chunks, docs, index = load_store()
    kiwi = Kiwi()
    model = SentenceTransformer(EMBED_MODEL)
    reranker = CrossEncoder(RERANK_MODEL, max_length=RERANK_MAX_LEN)

    with open(ROOT / "eval" / "concepts.csv", encoding="utf-8") as f:
        concepts = list(csv.DictReader(f))
    n = len(concepts)

    # 1. Recall@k, MRR: RRF 10개, 리랭크 후 3개
    ranks = {}  # 개념 id → 처음 맞힌 등수 (못 맞히면 None)
    rerank_ranks = {}
    for c in concepts:
        answers = c["answers"].split(";")
        found = search(c["concept"], kiwi, model, chunks, docs, index)
        ranks[c["id"]] = first_hit_rank([ch["id"] for ch in found], answers)
        kept = rerank(c["concept"], found, reranker)
        rerank_ranks[c["id"]] = first_hit_rank([ch["id"] for ch in kept], answers)

    def report(name: str, ranks: dict, ks: tuple[int, ...]) -> str:
        recall = "  ".join(f"R@{k} {sum(r is not None and r <= k for r in ranks.values()) / n:.2f}" for k in ks)
        mrr = sum(1 / r for r in ranks.values() if r) / n
        return f"{name}  {recall}  MRR {mrr:.3f}"

    # 2. HNSW vs 전부 비교: 개념마다 상위 TOP_K가 얼마나 겹치나
    exact = faiss.IndexFlatIP(index.d)
    exact.add(index.reconstruct_n(0, index.ntotal))
    overlaps = []
    for c in concepts:
        hnsw_ids = set(search_vector(c["concept"], model, index, TOP_K))
        exact_ids = set(search_vector(c["concept"], model, exact, TOP_K))
        overlaps.append(len(hnsw_ids & exact_ids) / TOP_K)

    print(f"개념 {n}개, 조각 {len(chunks)}개")
    print(report(f"RRF {TOP_K}개   ", ranks, (1, 3, 5, 10)))
    print(report(f"리랭크 {RERANK_KEEP}개", rerank_ranks, (1, 3)))
    print(f"HNSW vs 전부 비교 겹침 {sum(overlaps) / n:.2f}")
    misses = [f"{c['id']}({c['concept']}):{rerank_ranks[c['id']] or '-'}" for c in concepts if rerank_ranks[c["id"]] != 1]
    print("리랭크 후 1등 아님: " + (", ".join(misses) or "없음"))

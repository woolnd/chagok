"""임베딩과 BM25 검색 결과를 RRF로 합친다. 로컬 전용."""

import bm25
import reranker
import retriever

RRF_K = 60
CANDIDATES = 20
WEIGHT = 0.8
RERANK_THRESHOLD = None
PARENT = False


def search(query: str, k: int = 5, weight: float = WEIGHT) -> list[dict]:
    """임베딩과 BM25 결과를 RRF로 합쳐 상위 k개를 찾는다. PARENT면 ## 섹션으로 묶는다. 관련 없으면 빈 리스트."""
    retriev_candidates = retriever.search(query, CANDIDATES)
    bm25_candidates = bm25.search(query, CANDIDATES)

    scores = {}
    found = {}
    for candidates, w in ((retriev_candidates, weight), (bm25_candidates, 1 - weight)):
        for rank, chunk in enumerate(candidates, start=1):
            key = f"{chunk['file']}#{retriever.PATH_SEP.join(chunk['path'])}"
            scores[key] = scores.get(key, 0) + w / (RRF_K + rank)
            found[key] = chunk

    results = []
    originals = []
    seen = set()
    for key in sorted(scores, key=scores.get, reverse=True):
        chunk = found[key]
        if PARENT:
            chunk = {**chunk, "path": chunk["path"][:2]}
        parent = (chunk["file"], tuple(chunk["path"]))
        originals.append(found[key])
        if parent in seen:
            continue
        seen.add(parent)
        results.append(chunk)
        if len(results) == k:
            break
    if RERANK_THRESHOLD is not None and reranker.max_score(query, originals) < RERANK_THRESHOLD:
        return []
    return results

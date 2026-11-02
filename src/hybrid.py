"""임베딩과 BM25 검색 결과를 RRF로 합친다. 로컬 전용."""

import bm25
import reranker
import retriever

RRF_K = 60  # RRF 공식의 상수. 논문 기본값
CANDIDATES = 20  # 각 검색에서 가져올 후보 수
WEIGHT = 0.8  # 임베딩 비중. 0.8 / 0.5 / 0.2 중 채택. docs/DECISIONS.md
THRESHOLD = None
# 리랭커 최고점 기준선. None이면 끔. 이보다 낮으면 결과 없음 (#29)
RERANK_THRESHOLD = None


def search(query: str, k: int = 5, weight: float = WEIGHT) -> list[dict]:
    # 1. 임베딩 검색 후보 CANDIDATES개
    # 2. BM25 검색 후보 CANDIDATES개
    # 3. 청크마다 RRF 점수 더하기
    # 4. 점수 높은 순으로 k개 돌려주기

    retriev_candidates = retriever.search(query, CANDIDATES)

    if THRESHOLD is not None and retriev_candidates[0]["distance"] >= THRESHOLD:
        return []
    bm25_candidates = bm25.search(query, CANDIDATES)

    scores = {}  # 이름표: RRF 점수
    found = {}  # 이름표: 청크. 돌려줄 내용을 보관한다
    # 두 검색은 점수 단위가 달라(거리 / BM25 점수) 등수만 쓴다
    for candidates, w in ((retriev_candidates, weight), (bm25_candidates, 1 - weight)):
        for rank, chunk in enumerate(candidates, start=1):
            key = f"{chunk['file']}#{retriever.PATH_SEP.join(chunk['path'])}"
            # 양쪽에 다 나온 청크는 점수가 더해져 올라간다
            scores[key] = scores.get(key, 0) + w / (RRF_K + rank)
            found[key] = chunk

    top = sorted(scores, key=scores.get, reverse=True)[:k]
    results = [found[key] for key in top]
    # 게이트 1: 리랭커가 최종 결과를 읽어 보고, 가장 관련 있는 것도 낮으면 노트에 없다고 본다
    if RERANK_THRESHOLD is not None and reranker.max_score(query, results) < RERANK_THRESHOLD:
        return []
    return results

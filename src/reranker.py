"""질문과 청크를 같이 읽고 관련 정도를 채점한다. 로컬 전용."""

from functools import cache

import torch
from sentence_transformers import CrossEncoder

from retriever import PATH_SEP

MODEL = "dragonkue/bge-reranker-v2-m3-ko"
MAX_LENGTH = 256  # 512보다 빠르고 점수 차이 없음 (#29 실험)


@cache
def get_reranker() -> CrossEncoder:
    """리랭커 모델. 2GB라 한 번만 불러온다."""
    # CI(리눅스)에는 GPU가 없어 CPU로 돌린다
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    reranker = CrossEncoder(MODEL, max_length=MAX_LENGTH, device=device)
    # fp16은 GPU에서만 빠르다. CPU에서는 느리거나 오류가 난다
    if device == "mps":
        reranker.model.half()

    return reranker


def max_score(query: str, chunks: list[dict]) -> float:
    """질문과 청크들을 짝지어 채점하고 가장 높은 점수를 돌려준다."""
    # 색인할 때처럼 제목 경로를 붙여야 "패딩"이 어느 노트 것인지 알 수 있다
    pairs = [(query, PATH_SEP.join(c["path"]) + "\n" + c["text"]) for c in chunks]
    # 0~1로 바꾸면 관련 없는 질문 점수가 모두 0.000으로 뭉개져 기준선을 긋기 어렵다
    scores = get_reranker().predict(pairs, activation_fn=torch.nn.Identity())
    return float(max(scores))

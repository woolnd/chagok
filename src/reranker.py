"""질문과 청크를 같이 읽고 관련 정도를 채점한다. 로컬 전용."""

from functools import cache

import torch
from sentence_transformers import CrossEncoder

from retriever import PATH_SEP

MODEL = "dragonkue/bge-reranker-v2-m3-ko"
MAX_LENGTH = 256
THRESHOLD = -9.6


@cache
def get_reranker() -> CrossEncoder:
    """리랭커 모델. 2GB라 한 번만 불러온다."""
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    reranker = CrossEncoder(MODEL, max_length=MAX_LENGTH, device=device)
    if device == "mps":
        reranker.model.half()

    return reranker


def max_score(query: str, chunks: list[dict]) -> float:
    """질문과 청크들을 짝지어 채점하고 가장 높은 점수를 돌려준다."""
    pairs = [(query, PATH_SEP.join(c["path"]) + "\n" + c["text"]) for c in chunks]
    scores = get_reranker().predict(pairs, activation_fn=torch.nn.Identity())
    return float(max(scores))

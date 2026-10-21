"""kiwi로 형태소를 잘라 BM25로 청크를 찾는다. 로컬 전용."""

from functools import cache
from pathlib import Path

from kiwipiepy import Kiwi
from rank_bm25 import BM25Okapi

from chunker import chunk
from parser import NOTES_DIR

# 명사·동사·형용사·영어·숫자만. 조사·어미·기호는 검색에 도움이 안 된다
KEEP_TAGS = {"NNG", "NNP", "VV", "VA", "SL", "SN"}


@cache
def get_kiwi() -> Kiwi:
    """형태소 분석기. 처음 만들 때 느려서 한 번만 만든다."""
    return Kiwi()


def tokenize(text: str) -> list[str]:
    """글을 형태소로 잘라 검색에 쓸 단어만 남긴다."""
    tokens = get_kiwi().tokenize(text)
    # 불규칙 활용은 "VA-I"처럼 붙어 나와서 앞부분만 본다
    return [token.form for token in tokens if token.tag.split("-")[0] in KEEP_TAGS]

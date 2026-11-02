"""kiwi로 형태소를 잘라 BM25로 청크를 찾는다. 로컬 전용."""

from functools import cache
from pathlib import Path

from kiwipiepy import Kiwi
from rank_bm25 import BM25Okapi

from chunker import chunk
from parser import NOTES_DIR

KEEP_TAGS = {"NNG", "NNP", "VV", "VA", "SL", "SN"}
PATH_SEP = " > "


@cache
def get_kiwi() -> Kiwi:
    """형태소 분석기. 처음 만들 때 느려서 한 번만 만든다."""
    return Kiwi()


def tokenize(text: str) -> list[str]:
    """글을 형태소로 잘라 검색에 쓸 단어만 남긴다."""
    tokens = get_kiwi().tokenize(text)
    return [token.form for token in tokens if token.tag.split("-")[0] in KEEP_TAGS]


@cache
def get_index(notes_dir: Path = NOTES_DIR) -> tuple[BM25Okapi, list[dict]]:
    """노트 폴더의 청크로 BM25 색인을 만든다. 청크 목록도 같이 돌려준다."""
    notes = sorted(notes_dir.glob("*.md"))
    chunks = []
    corpus = []
    for note in notes:
        chunks.extend(chunk(note))

    for c in chunks:
        text = PATH_SEP.join(c["path"]) + "\n" + c["text"]
        corpus.append(tokenize(text))

    return BM25Okapi(corpus), chunks


def search(query: str, k: int = 5) -> list[dict]:
    """질문과 단어가 겹치는 청크를 찾는다. retriever.search와 같은 모양이다."""
    query_tokens = tokenize(query)
    bm25, chunks = get_index()
    scores = bm25.get_scores(query_tokens)

    results = []
    for i in scores.argsort()[::-1][:k]:
        c = chunks[i]
        results.append(
            {
                "file": c["file"],
                "date": str(c["date"]),
                "path": c["path"],
                "text": c["text"],
                "score": float(scores[i]),
            }
        )
    return results

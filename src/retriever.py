"""청크를 임베딩해 Chroma에 색인하고, 질문으로 청크를 찾는다. 로컬 전용."""

from functools import cache
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from chunker import chunk
from parser import NOTES_DIR

CHROMA_DIR = Path("data/chroma")  # 프로젝트 루트 기준
PATH_SEP = " > "


@cache
def get_model() -> SentenceTransformer:
    """임베딩 모델. 2GB라 한 번만 불러와 색인과 검색이 같이 쓴다."""
    return SentenceTransformer("BAAI/bge-m3")


@cache
def get_collection() -> chromadb.Collection:
    """청크 컬렉션. 없으면 만든다."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    # 기본값은 L2 거리. 정규화한 bge-m3 벡터는 cosine으로 비교한다
    collection = client.get_or_create_collection(
        "notes", configuration={"hnsw": {"space": "cosine"}}
    )
    return collection


def build_index(notes_dir: Path = NOTES_DIR) -> int:
    """노트 폴더의 모든 청크를 임베딩해 Chroma에 저장한다.

    Args:
        notes_dir: 노트 폴더 경로.

    Returns:
        색인한 청크 수.
    """
    chunks = [c for path in sorted(notes_dir.glob("*.md")) for c in chunk(path)]
    # 제목 경로를 붙여야 "패딩"이 CNN 것인지 NLP 것인지 구분된다. 저장은 원문만
    texts = [PATH_SEP.join(c["path"]) + "\n" + c["text"] for c in chunks]
    # 길이를 1로 맞춰 cosine 유사도로 비교한다
    embeddings = get_model().encode(texts, normalize_embeddings=True)

    # 순번 id는 노트가 추가되면 밀려서 엉뚱한 청크를 덮어쓴다
    ids = [c["file"] + "#" + PATH_SEP.join(c["path"]) for c in chunks]
    # Chroma 메타데이터는 리스트·date를 받지 않아 문자열로 바꾼다
    metadatas = [
        {"file": c["file"], "date": str(c["date"]), "path": PATH_SEP.join(c["path"])}
        for c in chunks
    ]

    collection = get_collection()
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=[c["text"] for c in chunks],
        metadatas=metadatas,
    )
    # upsert는 지운 섹션을 남겨 두므로, 이번 색인에 없는 id는 지운다
    stale = set(collection.get(include=[])["ids"]) - set(ids)
    if stale:
        collection.delete(ids=list(stale))
    return len(ids)

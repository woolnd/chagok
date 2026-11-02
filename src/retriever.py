"""청크를 임베딩해 Chroma에 색인하고, 질문으로 청크를 찾는다. 로컬 전용."""

import hashlib
from functools import cache
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from chunker import chunk
from parser import NOTES_DIR

CHROMA_DIR = Path("data/chroma")
PATH_SEP = " > "


@cache
def get_model() -> SentenceTransformer:
    """임베딩 모델. 2GB라 한 번만 불러와 색인과 검색이 같이 쓴다."""
    return SentenceTransformer("BAAI/bge-m3")


@cache
def get_collection() -> chromadb.Collection:
    """청크 컬렉션. 없으면 만든다."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(
        "notes", configuration={"hnsw": {"space": "cosine"}}
    )
    return collection


def build_index(notes_dir: Path = NOTES_DIR) -> int:
    """노트 폴더의 청크를 Chroma에 저장한다. 바뀐 청크만 다시 임베딩한다."""
    chunks = [c for path in sorted(notes_dir.glob("*.md")) for c in chunk(path)]
    ids = [c["file"] + "#" + PATH_SEP.join(c["path"]) for c in chunks]
    texts = [PATH_SEP.join(c["path"]) + "\n" + c["text"] for c in chunks]
    hashes = [hashlib.sha256(t.encode()).hexdigest() for t in texts]

    collection = get_collection()
    saved = collection.get(include=["metadatas"])
    saved_hash = {
        id_: meta.get("hash") for id_, meta in zip(saved["ids"], saved["metadatas"])
    }
    changed = [i for i, id_ in enumerate(ids) if saved_hash.get(id_) != hashes[i]]

    if changed:
        collection.upsert(
            ids=[ids[i] for i in changed],
            embeddings=get_model().encode(
                [texts[i] for i in changed], normalize_embeddings=True
            ),
            documents=[chunks[i]["text"] for i in changed],
            metadatas=[
                {
                    "file": chunks[i]["file"],
                    "date": str(chunks[i]["date"]),
                    "path": PATH_SEP.join(chunks[i]["path"]),
                    "hash": hashes[i],
                }
                for i in changed
            ],
        )
    stale = set(saved["ids"]) - set(ids)
    if stale:
        collection.delete(ids=list(stale))
    return len(ids)


def search(query: str, k: int = 5) -> list[dict]:
    """질문과 가까운 청크를 찾는다. 검색만 하고 생성은 하지 않는다."""
    query_embedding = get_model().encode(query, normalize_embeddings=True)
    result = get_collection().query(query_embeddings=[query_embedding], n_results=k)

    chunks = []
    for meta, text, distance in zip(
        result["metadatas"][0], result["documents"][0], result["distances"][0]
    ):
        chunks.append(
            {
                "file": meta["file"],
                "date": meta["date"],
                "path": meta["path"].split(PATH_SEP),
                "text": text,
                "distance": distance,
            }
        )
    return chunks

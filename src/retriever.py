"""청크를 임베딩해 Chroma에 색인하고, 질문으로 청크를 찾는다. 로컬 전용."""

import hashlib
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
    """노트 폴더의 청크를 Chroma에 저장한다. 바뀐 청크만 다시 임베딩한다.

    Args:
        notes_dir: 노트 폴더 경로.

    Returns:
        색인한 청크 수.
    """
    chunks = [c for path in sorted(notes_dir.glob("*.md")) for c in chunk(path)]
    # 순번 id는 노트가 추가되면 밀려서 엉뚱한 청크를 덮어쓴다
    ids = [c["file"] + "#" + PATH_SEP.join(c["path"]) for c in chunks]
    # 제목 경로를 붙여야 "패딩"이 CNN 것인지 NLP 것인지 구분된다. 저장은 원문만
    texts = [PATH_SEP.join(c["path"]) + "\n" + c["text"] for c in chunks]
    # 임베딩에 들어가는 글로 만들어야 소제목만 바뀐 경우도 잡힌다
    hashes = [hashlib.sha256(t.encode()).hexdigest() for t in texts]

    collection = get_collection()
    saved = collection.get(include=["metadatas"])
    saved_hash = {
        id_: meta.get("hash") for id_, meta in zip(saved["ids"], saved["metadatas"])
    }
    # 저장된 해시와 다르거나(내용 수정) 없는(새 청크·예전 색인) 것만 다시 임베딩한다
    changed = [i for i, id_ in enumerate(ids) if saved_hash.get(id_) != hashes[i]]

    # 빈 리스트는 upsert가 거부한다. 바뀐 게 없으면 bge-m3도 불러오지 않는다
    if changed:
        collection.upsert(
            ids=[ids[i] for i in changed],
            # 길이를 1로 맞춰 cosine 유사도로 비교한다
            embeddings=get_model().encode(
                [texts[i] for i in changed], normalize_embeddings=True
            ),
            documents=[chunks[i]["text"] for i in changed],
            # Chroma 메타데이터는 리스트·date를 받지 않아 문자열로 바꾼다
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
    # upsert는 지운 섹션을 남겨 두므로, 이번 색인에 없는 id는 지운다
    stale = set(saved["ids"]) - set(ids)
    if stale:
        collection.delete(ids=list(stale))
    return len(ids)


def search(query: str, k: int = 5) -> list[dict]:
    """질문과 가까운 청크를 찾는다. 검색만 하고 생성은 하지 않는다.

    Args:
        query: 질문.
        k: 돌려줄 청크 수.

    Returns:
        가까운 순서의 청크 리스트. 청크마다 {"file", "date", "path", "text", "distance"}.
        date는 "YYYY-MM-DD" 문자열, distance는 cosine 거리(0에 가까울수록 비슷함).
    """
    # 질문은 경로 없이 그대로. 색인과 같은 모델·정규화여야 벡터끼리 비교된다
    query_embedding = get_model().encode(query, normalize_embeddings=True)
    result = get_collection().query(query_embeddings=[query_embedding], n_results=k)

    chunks = []
    # query는 질문 여러 개를 받으므로 결과도 질문마다 리스트다. 질문 하나라 [0]
    for meta, text, distance in zip(
        result["metadatas"][0], result["documents"][0], result["distances"][0]
    ):
        chunks.append(
            {
                "file": meta["file"],
                "date": meta["date"],
                "path": meta["path"].split(PATH_SEP),  # chunk와 같은 리스트로 되돌림
                "text": text,
                "distance": distance,
            }
        )
    return chunks

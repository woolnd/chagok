"""적재: 조각을 BM25용 단어 목록과 FAISS 벡터로 저장한다.

흐름
    raw/*.md
      │ parse_note → make_chunks     조각 목록 [{id, text, file, page, ...}, ...]
      │ save_chunks                  조각 원본 → store/chunks.json
      │ save_bm25                    kiwi 형태소 → store/bm25_tokens.json
      │ save_faiss                   bge-m3 벡터 → store/faiss.index
      ▼
    store/ (세 파일 모두 같은 순서: i번째 = i번째 조각)

규칙 (기획서 처음 값)
    - BM25(kiwi 형태소) + 벡터 동시 저장, 검색 때 RRF로 합침
    - 임베딩 모델: bge-m3 (BAAI/bge-m3)
    - 벡터 저장소: FAISS HNSW, M = 16, ef_search = 64
    - 새 노트가 생기면 raw/ 전체를 다시 적재한다
"""

import json  # 조각·단어 목록을 파일로 저장
from pathlib import Path  # 경로

import faiss  # 벡터 저장소 (HNSW)
from kiwipiepy import Kiwi  # 한국어 형태소 분석
from sentence_transformers import SentenceTransformer  # bge-m3 임베딩

from chagok.chunk import make_chunks
from chagok.parse import parse_note

ROOT = Path(__file__).parents[2]
RAW = ROOT / "raw"
STORE = ROOT / "store"

# BM25에 남길 kiwi 품사
#   남김: NNG 일반명사(기울기), NNP 고유명사, SL 영어(LSTM), SN 숫자(0),
#         VV 동사(넘다), VA 형용사(작다), XR 어근(복잡하다의 "복잡")
#   버림: J* 조사(은·를), E* 어미(었·다), X* 접사(하·들), S* 문장부호(. ,),
#         NNB 의존명사(것·수), MAG 부사(그대로) — 뜻이 거의 없어 검색에 방해
KEEP_TAGS = {"NNG", "NNP", "SL", "SN", "VV", "VA", "XR"}

EMBED_MODEL = "BAAI/bge-m3"
HNSW_M = 16
EF_SEARCH = 64


def load_chunks(raw: Path) -> list[dict]:
    """raw/의 노트를 전부 파싱·청킹해서 조각 목록으로 만든다."""
    paths = sorted(raw.glob("*.md"))
    chunks = []
    for path in paths:
        note = parse_note(path)
        note_chunks = make_chunks(note)
        chunks.extend(note_chunks)

    return chunks


def save_chunks(chunks: list[dict], path: Path) -> None:
    """조각 원본을 json으로 저장한다. 검색 결과 번호 i → chunks[i]로 되찾을 때 쓴다."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)


def tokenize(kiwi: Kiwi, text: str) -> list[str]:
    """kiwi로 형태소를 잘라 BM25에 쓸 단어 목록으로 만든다.

    예: "기울기 소실 문제" → ["기울기", "소실", "문제"]
    """
    words = []
    tokens = kiwi.tokenize(text)
    for t in tokens:
        if t.tag in KEEP_TAGS:
            words.append(t.form)

    return words


def save_bm25(chunks: list[dict], path: Path) -> None:
    """조각마다 단어 목록을 만들어 json으로 저장한다. 점수 계산은 검색 단계에서."""
    kiwi = Kiwi()
    tokens = []
    for chunk in chunks:
        token = tokenize(kiwi, chunk["text"])
        tokens.append(token)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False)


def save_faiss(chunks: list[dict], path: Path) -> None:
    """조각을 bge-m3 벡터로 바꿔 FAISS HNSW 인덱스로 저장한다."""
    model = SentenceTransformer(EMBED_MODEL)
    texts = [chunk["text"] for chunk in chunks]

    # 길이 1로 맞추면 내적 = 코사인 유사도. 결과 모양: (조각 수, 1024)
    vectors = model.encode(texts, normalize_embeddings=True)

    index = faiss.IndexHNSWFlat(vectors.shape[1], HNSW_M, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efSearch = EF_SEARCH
    index.add(vectors)

    faiss.write_index(index, str(path))


def ingest() -> None:
    """raw/ 전체를 적재한다. 새 노트가 생기면 이것만 다시 돌린다."""
    STORE.mkdir(exist_ok=True)
    chunks = load_chunks(RAW)
    save_chunks(chunks, STORE / "chunks.json")
    save_bm25(chunks, STORE / "bm25_tokens.json")
    save_faiss(chunks, STORE / "faiss.index")


if __name__ == "__main__":
    # raw/ 전체를 적재하고 확인 (실행: uv run python -m chagok.store)
    ingest()

    chunks = json.loads((STORE / "chunks.json").read_text(encoding="utf-8"))
    tokens = json.loads((STORE / "bm25_tokens.json").read_text(encoding="utf-8"))
    index = faiss.read_index(str(STORE / "faiss.index"))

    # 세 파일의 개수가 조각 수와 같은지 (i번째 = i번째 조각)
    assert len(chunks) == len(load_chunks(RAW)), len(chunks)
    assert len(tokens) == len(chunks), len(tokens)
    assert index.ntotal == len(chunks), index.ntotal

    # 단어 목록: 비어 있는 조각이 없고, 조사·어미는 빠졌는지
    c = next(i for i, ch in enumerate(chunks) if ch["id"].endswith("퍼셉트론 > 1. 퍼셉트론이란"))
    assert all(tokens), [chunks[i]["id"] for i, t in enumerate(tokens) if not t]
    assert "퍼셉트론" in tokens[c] and "은" not in tokens[c], tokens[c][:20]

    # FAISS 설정값, 조각마다 자기 벡터로 검색하면 1등이 자기 자신인지
    assert (index.d, index.hnsw.efSearch) == (1024, EF_SEARCH)
    vectors = index.reconstruct_n(0, index.ntotal)
    _, top = index.search(vectors, 1)
    assert all(top[i][0] == i for i in range(len(chunks))), [i for i in range(len(chunks)) if top[i][0] != i]

    print(f"조각 {len(chunks)}개 → chunks.json, bm25_tokens.json, faiss.index 저장")
    print(f"첫 조각 단어 {len(tokens[0])}개: {tokens[0][:10]}")
    print("OK")

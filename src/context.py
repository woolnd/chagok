"""섹션마다 노트 안에서 무엇에 대한 내용인지 한 문장 맥락을 Claude로 만든다. 로컬 전용."""

import hashlib
import json
from functools import cache
from pathlib import Path

import anthropic

from chunker import chunk
from parser import NOTES_DIR
from retriever import PATH_SEP

MODEL = "claude-haiku-5-5"
CONTEXT_PATH = Path("data/contexts.json")


@cache
def get_client() -> anthropic.Anthropic:
    """Claude API 클라이언트. 키는 환경 변수 ANTHROPIC_API_KEY에서 읽는다."""
    return anthropic.Anthropic()


def chunk_text(c: dict) -> str:
    """색인할 때와 같은 제목 경로 + 본문."""
    return PATH_SEP.join(c["path"]) + "\n" + c["text"]


def chunk_hash(c: dict) -> str:
    """섹션 글이 바뀌었는지 알아보는 이름표."""
    return hashlib.sha256(chunk_text(c).encode()).hexdigest()


def make_context(note_text: str, c: dict) -> str:
    """섹션 하나가 노트 안에서 무엇에 대한 내용인지 한 문장으로 만든다."""
    response = get_client().messages.create(
        model=MODEL,
        max_tokens=1024,
        output_config={"effort": "low"},
        system=[
            {
                "type": "text",
                "text": f"<documents>{note_text}</documents>",
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"<chunk>{chunk_text(c)}</chunk>\n"
                "이 섹션이 노트 안에서 무엇에 대한 내용인지 한 문장으로 써라. "
                "검색에 쓰이도록 핵심 용어를 넣고, 문장만 답하라.",
            }
        ],
    )
    return next(b.text for b in response.content if b.type == "text").strip()


def load_contexts() -> dict:
    """저장된 맥락. {섹션 해시: 맥락}. 없으면 빈 딕셔너리."""
    if not CONTEXT_PATH.exists():
        return {}
    return json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))


def build_contexts(notes_dir: Path = NOTES_DIR) -> int:
    """맥락이 없는 섹션만 만들어 저장하고, 새로 만든 수를 돌려준다."""
    contexts = load_contexts()
    made = 0
    for path in sorted(notes_dir.glob("*.md")):
        note_text = path.read_text(encoding="utf-8")
        for c in chunk(path):
            h = chunk_hash(c)
            if h in contexts:
                continue
            contexts[h] = make_context(note_text, c)
            made += 1
            print(f"{c['file']}#{PATH_SEP.join(c['path'])}\n  {contexts[h]}")
    CONTEXT_PATH.write_text(
        json.dumps(contexts, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return made


if __name__ == "__main__":
    print(f"새로 만든 맥락 {build_contexts()}개")

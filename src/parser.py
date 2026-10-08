"""노트 마크다운 파서. 노트 파일은 읽기 전용."""

from collections import Counter
from pathlib import Path
import frontmatter
from markdown_it import MarkdownIt

NOTES_DIR = Path("data/notes")  # 프로젝트 루트 기준
markdown_parser = MarkdownIt("commonmark")  # 표(table)는 미지원


def parse(path: Path) -> dict:
    """노트 하나를 파싱한다.

    Args:
        path: 노트 파일 경로.

    Returns:
        file, date, title, sections, heading_count, memos 키를 가진 dict.
        date는 datetime.date, 없으면 None. title은 첫 번째 h1.
        sections는 h2·h3마다 {"path": [h1, (h2,) 현재 제목]}.
        heading_count는 {제목 레벨: 개수}로, 형식 검사(h1 한 번, h4 이하 금지)에 쓴다.
        memos는 "> 메모:" 줄마다 {"path": 메모가 있던 제목 경로, "text": "메모:" 뒤 내용}.
    """
    post = frontmatter.load(path)
    # 코드 블록 안의 #은 fence 토큰에 포함되므로 heading으로 잡히지 않는다
    token_list = markdown_parser.parse(post.content)
    title = None
    heading_path = []
    sections = []
    heading_count = Counter()
    memos = []

    for index, token in enumerate(token_list):
        # 인용 안 문단만 본다. 본문의 "메모리" 같은 단어가 걸리지 않게 하려고
        # index >= 2는 음수 인덱스가 리스트 끝을 가리키는 것을 막는다
        if (
            token.type == "inline"
            and index >= 2
            and token_list[index - 2].type == "blockquote_open"
        ):
            # 연속된 "> 메모:" 줄은 inline 토큰 하나로 합쳐지므로 줄 단위로 나눈다
            for line in token.content.splitlines():
                if line.startswith("메모:"):
                    memos.append(
                        {
                            "path": heading_path,
                            "text": line.removeprefix("메모:").strip(),
                        }
                    )

        if token.type != "heading_open":
            continue
        text = token_list[index + 1].content  # 다음 토큰(inline)이 제목 텍스트
        level = int(token.tag[1])  # "h2" → 2
        heading_count[level] += 1  # 분기 전에 세야 h4 이상도 빠지지 않는다

        if level == 1:
            if title is None:
                title = text
                heading_path = [text]
        elif level in (2, 3):
            # 상위 제목만 남기고 붙인다. 새 h2가 오면 이전 h3는 잘린다
            heading_path = heading_path[: level - 1] + [text]
            sections.append({"path": heading_path})

    return {
        "file": path.name,
        "date": post.metadata.get("date"),
        "title": title,
        "sections": sections,
        "heading_count": dict(heading_count),
        "memos": memos,
    }


if __name__ == "__main__":
    for path in sorted(NOTES_DIR.glob("*.md")):
        print(parse(path))

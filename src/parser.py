"""노트 마크다운 파서. 노트 파일은 읽기 전용."""

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
        file, date, title 키를 가진 dict. date는 datetime.date, 없으면 None.
    """
    post = frontmatter.load(path)
    # 코드 블록 안의 #은 fence 토큰에 포함되므로 heading으로 잡히지 않는다
    token_list = markdown_parser.parse(post.content)
    title = None

    for index, token in enumerate(token_list):
        if token.type == "heading_open" and token.tag == "h1":
            title = token_list[index + 1].content  # 다음 토큰(inline)이 제목 텍스트
            break

    return {"file": path.name, "date": post.metadata.get("date"), "title": title}


if __name__ == "__main__":
    for path in sorted(NOTES_DIR.glob("*.md")):
        print(parse(path))

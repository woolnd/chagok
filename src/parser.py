"""노트 마크다운 파서. 노트 파일은 읽기만 하고, 형식 판정은 format_check가 한다."""

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
        다음 키를 가진 dict.
        - file: 파일 이름.
        - date: 프론트매터 date. YAML이 날짜로 읽으면 datetime.date, 없으면 None.
        - title: 첫 번째 h1 텍스트. 없으면 None.
        - sections: h2·h3마다 {"path": [h1, (h2,) 현재 제목], "text": 다음 제목 전까지의 원문}.
        - heading_count: {제목 레벨: 개수}. 형식 검사용.
        - code_without_lang_count: 언어 표시 없는 코드 블록 수. 형식 검사용.
    """
    post = frontmatter.load(path)
    # 코드 블록 안의 #은 fence 토큰에 포함되므로 heading으로 잡히지 않는다
    tokens = markdown_parser.parse(post.content)
    lines = post.content.splitlines()  # token.map 줄 번호와 같은 기준

    # (레벨, 제목, 제목 줄 범위). 다음 토큰(inline)이 제목 텍스트
    headings = [
        (int(token.tag[1]), tokens[i + 1].content, token.map)
        for i, token in enumerate(tokens)
        if token.type == "heading_open"
    ]

    title = None
    heading_path = []
    sections = []
    for i, (level, text, line_range) in enumerate(headings):
        if level == 1 and title is None:
            title = text
            heading_path = [text]
        elif level in (2, 3):
            # 상위 제목만 남기고 붙인다. 새 h2가 오면 이전 h3는 잘린다
            heading_path = heading_path[: level - 1] + [text]
            # 본문은 다음 제목(레벨 무관) 전까지, 마지막이면 노트 끝까지
            end = headings[i + 1][2][0] if i + 1 < len(headings) else len(lines)
            body = "\n".join(lines[line_range[1] : end]).strip()
            sections.append({"path": heading_path, "text": body})

    return {
        "file": path.name,
        "date": post.metadata.get("date"),
        "title": title,
        "sections": sections,
        "heading_count": dict(Counter(level for level, _, _ in headings)),
        "code_without_lang_count": sum(
            t.type == "fence" and not t.info.strip() for t in tokens
        ),
    }


if __name__ == "__main__":
    for path in sorted(NOTES_DIR.glob("*.md")):
        print(parse(path))

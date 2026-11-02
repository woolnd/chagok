"""노트 마크다운 파서. 노트 파일은 읽기만 하고, 형식 판정은 format_check가 한다."""

from collections import Counter
from pathlib import Path
import frontmatter
from markdown_it import MarkdownIt

NOTES_DIR = Path("data/notes")
markdown_parser = MarkdownIt("commonmark")


def parse(path: Path) -> dict:
    """노트 하나를 파싱한다."""
    post = frontmatter.load(path)
    tokens = markdown_parser.parse(post.content)
    lines = post.content.splitlines()

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
            heading_path = heading_path[: level - 1] + [text]
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

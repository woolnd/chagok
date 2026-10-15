"""노트 형식 검사. parse() 결과만 보고 판정하고, 노트 파일은 고치지 않는다."""

import datetime
from collections import Counter

# src/를 스크립트 경로로 실행해야 같은 폴더의 parser를 찾는다
from parser import NOTES_DIR, parse


def check(note: dict) -> list[str]:
    """노트 하나의 형식 위반 사항을 모은다.

    Args:
        note: parse()가 돌려준 dict.

    Returns:
        위반 메시지 리스트. 비어 있으면 통과.
    """
    errors = []

    date = note["date"]
    if date is None:
        errors.append("date 없음")
    # datetime은 date의 하위 타입이라 isinstance로는 시간이 붙은 값을 못 거른다
    elif type(date) is not datetime.date:
        errors.append(f"date 형식 오류: {date!r} (YYYY-MM-DD, 따옴표 없이)")

    heading_count = note["heading_count"]
    h1_count = heading_count.get(1, 0)
    deep_count = sum(n for level, n in heading_count.items() if level >= 4)
    if h1_count != 1:
        errors.append(f"# 제목 개수 오류: {h1_count}개 (1개여야 함)")
    if deep_count >= 1:
        errors.append(f"#### 이하 제목 사용: {deep_count}개 (###까지만)")

    lang_count = note["code_without_lang_count"]
    if lang_count >= 1:
        errors.append(f"코드 블록 언어 표시 없음: {lang_count}개 (```python 처럼)")

    # 서론과 빈 섹션은 청크가 되지 않아, 이대로면 노트가 검색에서 통째로 빠진다
    if not any(s["text"] for s in note["sections"]):
        errors.append("내용 있는 ##·### 섹션 없음 (검색에 안 잡힘)")

    # 청크 id가 "파일#제목 경로"라 경로가 겹치면 색인이 멈춘다
    paths = Counter(" > ".join(s["path"]) for s in note["sections"])
    duplicates = [p for p, n in paths.items() if n >= 2]
    if duplicates:
        errors.append(f"같은 제목 경로 중복: {', '.join(duplicates)}")

    return errors


if __name__ == "__main__":
    paths = sorted(NOTES_DIR.glob("*.md"))
    passed = 0
    for path in paths:
        errors = check(parse(path))
        passed += not errors
        print(path.name, errors or "통과")
    print(f"통과 {passed} / 전체 {len(paths)}")

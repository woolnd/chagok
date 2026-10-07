#!/bin/bash
# 사람만 수정하는 파일(eval/, docs/DESIGN.md, docs/QA_CRITERIA.md)의 Write/Edit를 막는다.
path=$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')
rel=${path#"$CLAUDE_PROJECT_DIR"/}

case "$rel" in
  eval/*|docs/DESIGN.md|docs/QA_CRITERIA.md)
    echo "차단: $rel 은 사람만 수정합니다. 변경이 필요하면 사람에게 요청하세요." >&2
    exit 2
    ;;
esac

# 차곡 (chagok)

> 정리한 학습 노트로 평일마다 복습 문제 하나. 배운 내용을 머릿속에 차곡차곡.

내 학습 노트를 RAG로 검색해 서술형 복습 문제와 핵심 포인트를 만들고, 평일 하루 1개씩 메일로 보냅니다.

## 기능

- **복습 문제 메일**: 노트 근거로만 만든 서술형 문제 + 핵심 포인트 4~5개. 주말에 검토하고 평일에 발송.
- **Q&A 도우미** (로컬): 질문에 노트 근거로 답하고 출처를 표시.

## 구조

```
[로컬]  노트 → 정제 → 청킹 → 주제·키워드 추출 → 임베딩 → Chroma
        → 문제 생성 · 품질 점수 · 검토 화면 · Q&A
              ↓ 승인된 문제만
[서버]  보관 큐 → 스케줄러 → 평일 메일 (Railway)
```

## 기술 스택

Python · uv · Chroma · BM25 + kiwi · Claude API · LangGraph · Streamlit · FastAPI · Docker · Railway

## 원칙

- 노트에 없는 내용은 출제하지 않는다.
- 모든 모듈은 켰을 때 / 껐을 때를 수치로 비교한 뒤 채택한다. 결과는 [`docs/DECISIONS.md`](docs/DECISIONS.md).

## 문서

- [`CLAUDE.md`](CLAUDE.md): 프로젝트 기준 문서 (원칙, 아키텍처, 컨벤션)
- [`docs/DESIGN.md`](docs/DESIGN.md): 목표치·제약·품질 기준
- [`docs/STATUS.md`](docs/STATUS.md): 진행 상황

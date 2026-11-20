"""LLM Wiki: 노트로 개념 페이지(wiki/*.md)와 목차(wiki/index.md)를 만들고, 문제 낼 개념을 고른다.

흐름 (만들기: 새 노트가 생기면 적재 다음에)
    raw/ 노트 하나의 조각들
      │ extract_concepts   AI가 개념 이름 + 출처(조각 id)를 뽑음 → 출처가 실제 조각 id인지 코드로 확인
      │ tidy_concepts      전체 목록을 한 번에 보고 같은 개념을 하나로 합침 (빼기는 하지 않음)
      │ write_page         개념마다 출처 조각만 보고 AI가 정의·핵심 포인트·관련 개념을 씀
      │ save_page          wiki/{개념}.md 로 저장
      ▼
    index.md             새 개념을 "마지막 출제: -" 로 추가 (기존 개념의 날짜는 그대로)

흐름 (쓰기: 문제 만들 때)
    pick_concept         목차에서 오래 나오지 않은 개념 하나 (한 번도 안 나온 것부터)
    load_page            개념 페이지 → 검색 보강(전체 그림) + 채점 기준(핵심 포인트)
    mark_asked           문제를 냈으면 목차의 날짜를 오늘로

규칙 (기획서 처음 값)
    - raw/ 원본은 읽기만 한다. 문제의 근거는 항상 원문 조각에서 가져온다 (위키는 전체 그림)
    - 개념 하나당 페이지 하나: 정의, 핵심 포인트, 관련 개념 링크, 출처(어느 노트 몇 페이지)
    - 원문 용어는 바꿔 쓰지 않고 그대로 쓴다
    - 목차는 짧게: 개념 이름과 마지막으로 문제를 낸 날짜만
    - 켜고 끌 수 있다 (WIKI_ON). "검색만" vs "위키 + 검색"을 승인율로 비교하려고
"""

import re  # 소제목 꺼내기
from pathlib import Path  # 페이지 경로

import anthropic  # Claude API
from pydantic import BaseModel  # 출력 형식 (개념 목록, 개념 페이지)

from chagok.generate import MAX_TOKENS, format_chunks
from chagok.store import ROOT

WIKI_ON = True  # False면 위키 없이 "검색만"
WIKI_MODEL = "claude-haiku-5-5"
WIKI = ROOT / "wiki"
INDEX = WIKI / "index.md"

# 개념 뽑기 지시문 초안
EXTRACT_SYSTEM = """너는 학습 노트에서 복습할 개념을 뽑는 정리자다.
노트 조각들을 읽고, 복습 문제 하나를 낼 수 있는 개념을 뽑는다.

- 노트에서 따로 설명하고 있어서 서술형 문제 하나를 낼 수 있는 개념만 뽑는다. 다른 개념을 설명하다 잠깐 나오는 용어는 뽑지 않는다.
- 개념 이름은 노트에 쓰인 용어를 그대로 쓴다. 바꿔 부르거나 번역하지 않는다.
- "등장 배경", "두 단계 계산"처럼 개념이 아닌 소제목은 뽑지 않는다.
- 노트에서 용어 뒤 괄호에 붙인 영어 표기는 이름에 넣지 않는다. 예: "과대적합(overfitting)" → "과대적합"
- [이미 있는 개념]에 같은 개념이 있으면 그 이름을 글자 하나 바꾸지 않고 그대로 쓴다. 띄어쓰기만 다른 이름도 같은 개념이다.
- 같은 이름이 다른 뜻으로 쓰이면 띄어 쓴 괄호로 구분한다. 예: "패딩 (CNN)", "패딩 (자연어 처리)"
- 출처는 그 개념을 설명하는 조각의 "출처:" 값을 그대로 쓴다. 여러 개일 수 있다."""

# 개념 페이지 지시문 초안
PAGE_SYSTEM = """너는 학습 노트로 개념 페이지를 쓰는 정리자다.
주어진 노트 조각만 근거로 쓴다. 노트에 없는 내용은 넣지 않는다.

- 정의: 한두 문장. 노트의 표현을 최대한 그대로 쓴다.
- 핵심 포인트: 이 개념으로 문제를 낸다면 꼭 물어야 할 것. 3개 안팎.
- 관련 개념: 주어진 개념 목록 안에서만 고른다. 없으면 비운다."""


class Concept(BaseModel):
    """뽑은 개념 하나."""

    name: str  # 개념 이름 (노트 용어 그대로)
    sources: list[str]  # 출처 조각 id


class ConceptList(BaseModel):
    concepts: list[Concept]


# 정리 지시문 초안. 합치기만 한다 (개념이 아닌 용어는 문제 만들 때 걸러짐)
TIDY_SYSTEM = """너는 학습 노트에서 뽑은 개념 목록을 정리하는 정리자다.
목록 전체를 한 번에 보고, 다른 개념과 하나로 합쳐야 할 개념만 골라 into에 합칠 개념 이름을 목록에서 그대로 쓴다.
그대로 둘 개념은 쓰지 않는다. 개념을 빼지 않는다.

합치는 경우
- 같은 개념인데 표기만 다른 경우: 한글/영어, 약어, 띄어쓰기, 붙임표. 예: "skip 연결" → "스킵 연결", "bag-of-words" → "BoW"
- 노트에서 따로 설명하지 않고 다른 개념의 일부로만 나오는 경우. 예: "자연어" → "자연어 처리"

합치지 않는 경우
- 관련만 있는 다른 개념. 예: LSTM과 RNN, CBOW 모델과 skip-gram 모델, L1 정규화와 L2 정규화
- 노트에서 따로 설명하는 개념은 다른 개념의 일부여도 합치지 않는다. 예: Truncated SVD와 특잇값분해

[이미 있는 개념]은 바꾸지 않는다. 새 개념을 그쪽으로 합치는 것은 된다."""


class Change(BaseModel):
    """합치기 하나. 목록에 없는 개념은 그대로 둔다."""

    name: str  # 합칠 개념
    into: str  # 합쳐질 개념 이름


class Tidy(BaseModel):
    changes: list[Change]


class Page(BaseModel):
    """개념 페이지 내용. 출처는 Concept.sources를 그대로 쓴다 (AI가 쓰지 않음)."""

    definition: str  # 정의
    points: list[str]  # 핵심 포인트
    related: list[str]  # 관련 개념 이름


def extract_concepts(
    note_chunks: list[dict], known: list[str], client: anthropic.Anthropic
) -> list[Concept]:
    """노트 하나의 조각들 → AI → 개념 목록.

    - system=EXTRACT_SYSTEM, user = 이미 있는 개념 이름(known) + format_chunks(note_chunks)
    - known: 다른 노트에서 이미 뽑은 이름. 같은 개념은 같은 이름으로 뽑게 해서 페이지가 겹치지 않게
    - output_format=ConceptList, stop_reason 확인
    - 출처가 note_chunks의 id에 없으면 그 출처는 버림. 출처가 하나도 안 남으면 그 개념도 버림
    """
    user = (
        f"[이미 있는 개념]\n{', '.join(known) or '없음'}\n\n"
        f"[노트 조각]\n{format_chunks(note_chunks)}"
    )
    response = client.messages.parse(
        model=WIKI_MODEL,
        max_tokens=MAX_TOKENS,
        system=EXTRACT_SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_format=ConceptList,
    )

    if response.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(
            f"{note_chunks[0]['file']}: 개념 뽑기 실패 ({response.stop_reason})"
        )

    ids = {chunk["id"] for chunk in note_chunks}
    concepts = []

    for c in response.parsed_output.concepts:
        c.sources = [s for s in c.sources if s in ids]
        if c.sources:
            concepts.append(c)
    return concepts


def headings(concept: Concept, chunks: list[dict]) -> list[str]:
    """개념 출처 조각의 ## 소제목(조각 id 끝)과 ### 소제목(본문)."""
    found = []
    for chunk in chunks:
        if chunk["id"] in concept.sources:
            found.append(chunk["id"].split(" > ", 1)[1])
            found += re.findall(r"^### (.+)", chunk["text"], re.M)
    return found


def tidy_concepts(
    merged: dict[str, Concept], existing: list[str], chunks: list[dict], client: anthropic.Anthropic
) -> tuple[dict[str, Concept], list[str]]:
    """새 개념 목록 전체를 AI에 한 번 보여주고, 같은 개념을 하나로 합친다. 빼지는 않는다.

    - existing: 목차에 이미 있는 이름. 바꾸지 않고, 합칠 대상으로만 쓴다
    - into가 목록에 없거나 자기 자신이면 그 판단은 버림. A → B → C 처럼 이어지면 C로, 돌고 돌면 그대로
    출력: (정리된 새 개념, 합친 내역을 사람이 읽을 글로)
    """
    lines = [f"- {name} | 출처 소제목: {', '.join(headings(c, chunks))}" for name, c in merged.items()]
    user = (
        f"[이미 있는 개념]\n{', '.join(existing) or '없음'}\n\n"
        f"[새 개념]\n" + "\n".join(lines)
    )
    response = client.messages.parse(
        model=WIKI_MODEL,
        max_tokens=MAX_TOKENS,
        system=TIDY_SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_format=Tidy,
    )
    if response.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"개념 정리 실패 ({response.stop_reason})")

    targets = set(merged) | set(existing)
    into = {}  # 이름 → 합칠 이름
    for ch in response.parsed_output.changes:
        if ch.name in merged and ch.into in targets and ch.into != ch.name:
            into[ch.name] = ch.into

    def final(name: str) -> str:
        """A → B → C 를 따라가 마지막 이름. 돌고 돌면 처음 이름(그대로 둠)."""
        start, seen = name, {name}
        while name in into:
            name = into[name]
            if name in seen:
                return start
            seen.add(name)
        return name

    ends = {name: final(name) for name in into}
    tidied = {name: c for name, c in merged.items() if ends.get(name, name) == name}
    log = []
    for name, end in ends.items():
        if end == name:
            continue
        if end in tidied:
            tidied[end].sources += [s for s in merged[name].sources if s not in tidied[end].sources]
            log.append(f"합침: {name} → {end}")
        else:  # 이미 있는 개념으로 합침. ponytail: 그 페이지 출처는 그대로 (주간 점검에서)
            log.append(f"합침: {name} → {end} (이미 있는 개념)")
    return tidied, log


def write_page(
    concept: Concept, chunks: list[dict], names: list[str], client: anthropic.Anthropic
) -> Page:
    """개념 하나 → 출처 조각만 AI에 줘서 → Page.

    - chunks: 전체 조각. 이 중 concept.sources에 있는 것만 넘긴다
    - names: 관련 개념 후보(전체 개념 이름). related는 이 안에 있는 것만 남긴다
    - system=PAGE_SYSTEM, output_format=Page, stop_reason 확인
    """
    found = [c for c in chunks if c["id"] in concept.sources]
    user = (
        f"[개념]\n{concept.name}\n\n"
        f"[관련 개념 후보]\n{', '.join(names)}\n\n"
        f"[노트 조각]\n{format_chunks(found)}"
    )

    response = client.messages.parse(
        model=WIKI_MODEL,
        max_tokens=MAX_TOKENS,
        system=PAGE_SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_format=Page,
    )

    if response.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"{concept.name}: 페이지 쓰기 실패 ({response.stop_reason})")

    page = response.parsed_output
    page.related = [r for r in page.related if r in names and r != concept.name]
    return page


def page_path(name: str) -> Path:
    """개념 이름 → wiki/{이름}.md. 파일 이름에 못 쓰는 "/"는 "-"로."""
    return WIKI / f"{name.replace('/','-')}.md"


def save_page(concept: Concept, page: Page) -> None:
    """개념 페이지를 md로 저장한다.

    # 패딩 (CNN)

    ## 정의
    ...

    ## 핵심 포인트
    - ...

    ## 관련 개념
    - [[스트라이드]]

    ## 출처
    - 2026-10-21_cnn.md#합성곱 신경망(CNN) > 2. 합성곱 계층
    """
    lines = [
        f"# {concept.name}",
        "",
        "## 정의",
        page.definition,
        "",
        "## 핵심 포인트",
    ]
    lines += [f"- {p}" for p in page.points]
    lines += ["", "## 관련 개념"]
    lines += [f"- [[{r}]]" for r in page.related]
    lines += ["", "## 출처"]
    lines += [f"- {s}" for s in concept.sources]

    WIKI.mkdir(exist_ok=True)
    page_path(concept.name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_page(name: str) -> str:
    """개념 페이지 md를 그대로 읽는다. 검색 보강·채점 기준에 글 그대로 넘긴다."""
    return page_path(name).read_text(encoding="utf-8")


def load_index() -> dict[str, str]:
    """index.md → {개념 이름: 마지막 출제 날짜}. 한 번도 안 냈으면 "-".

    | 개념 | 마지막 출제 |
    |---|---|
    | 패딩 (CNN) | - |
    | 퍼셉트론 | 2026-11-20 |
    """
    if not INDEX.exists():
        return {}

    index = {}
    lines = INDEX.read_text(encoding="utf-8").splitlines()
    for line in lines[2:]:
        cells = line.split("|")
        index[cells[1].strip()] = cells[2].strip()

    return index


def save_index(index: dict[str, str]) -> None:
    """{개념 이름: 날짜} → index.md (위 표 모양)."""
    lines = ["| 개념 | 마지막 출제 |", "|---|---|"]
    lines += [f"| {name} | {date} |" for name, date in index.items()]
    WIKI.mkdir(exist_ok=True)
    INDEX.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(
    notes: list[str], chunks: list[dict], client: anthropic.Anthropic
) -> list[str]:
    """노트들(파일 이름)로 개념을 뽑아 페이지를 만들고 목차에 추가한다. 추가된 개념 이름을 돌려준다.

    - 이미 목차에 있는 개념은 건너뛴다 (날짜를 지우지 않게)
    - 처음엔 노트 전체, 그 뒤로는 새 노트만 넘긴다
    - 같은 이름이 여러 노트에서 나오면 출처를 합쳐 페이지 하나로
    """
    index = load_index()

    # 1. 노트마다 개념 뽑기, 같은 이름은 출처 합치기
    merged: dict[str, Concept] = {}
    for note in notes:
        note_chunks = [c for c in chunks if c["file"] == note]
        assert note_chunks, f"{note}: 조각이 없음 (적재를 먼저 돌렸는지)"
        concepts = extract_concepts(note_chunks, list(index) + list(merged), client)
        if not concepts:  # 출처가 전부 걸러진 경우. 조용히 넘어가면 노트 하나가 위키에서 빠짐
            raise RuntimeError(f"{note}: 뽑힌 개념이 없음 (출처가 모두 틀렸을 수 있음, 다시 돌리기)")
        for c in concepts:
            if c.name in merged:
                merged[c.name].sources += [s for s in c.sources if s not in merged[c.name].sources]
            else:
                merged[c.name] = c

    # 2. 정리: 같은 개념 합치기
    merged = {name: c for name, c in merged.items() if name not in index}
    if merged:
        merged, log = tidy_concepts(merged, list(index), chunks, client)
        print("\n".join(log) or "정리할 것 없음")

    # 3. 목차에 없는 개념만 페이지 쓰기
    # ponytail: 이미 있는 개념에 새 노트 출처가 생겨도 페이지는 그대로. 주간 점검에서 다룸
    # 핵심 포인트가 0개면 그 개념만 건너뜀: 노트에 설명이 거의 없어 문제를 낼 수 없음
    new = list(merged.values())
    names = list(index) + [c.name for c in new]
    pages, skipped = {}, []
    for c in new:
        page = write_page(c, chunks, names, client)
        if not page.points:
            skipped.append(c.name)
            print(f"건너뜀: {c.name} (핵심 포인트 0개)")
            continue
        save_page(c, page)
        pages[c.name] = (c, page)
        index[c.name] = "-"
        save_index(index)  # 페이지마다 저장: 중간에 멈춰도 만든 만큼은 목차에 남게

    # 건너뛴 개념으로 가는 관련 개념 링크는 지움 (먼저 쓴 페이지가 가리킬 수 있어서)
    for c, page in pages.values():
        if set(page.related) & set(skipped):
            page.related = [r for r in page.related if r not in skipped]
            save_page(c, page)

    return list(pages)


def pick_concept(index: dict[str, str]) -> str:
    """오래 나오지 않은 개념 하나. "-"(한 번도 안 냄)가 가장 오래된 것으로 친다."""
    return min(index, key=lambda name: index[name])


def mark_asked(name: str, date: str) -> None:
    """문제를 낸 개념의 목차 날짜를 바꾼다."""
    index = load_index()
    index[name] = date
    save_index(index)


if __name__ == "__main__":
    # 1. load_index / save_index / pick_concept / mark_asked (API 없이, 임시 폴더)
    # 2. 노트로 build → wiki/ 에 페이지·목차. 출처가 실제 조각 id인지, 관련 개념이 목차에 있는지
    # 실행: uv run --env-file .env python -m chagok.wiki [노트 파일 이름 ...]
    #       노트를 안 주면 아직 위키 출처에 없는 노트만 (다시 돌려도 이미 만든 노트는 다시 뽑지 않게)
    import sys
    import tempfile

    from chagok.search import load_store

    real_wiki, real_index = WIKI, INDEX
    WIKI = Path(tempfile.mkdtemp()) / "wiki"
    INDEX = WIKI / "index.md"
    assert load_index() == {}
    save_index({"퍼셉트론": "2026-11-20", "XOR 게이트": "-", "패딩 (CNN)": "2026-11-15"})
    assert pick_concept(load_index()) == "XOR 게이트"  # 한 번도 안 낸 것부터
    mark_asked("XOR 게이트", "2026-11-21")
    assert pick_concept(load_index()) == "패딩 (CNN)"  # 그다음 가장 오래된 날짜
    assert page_path("입력/출력").name == "입력-출력.md"
    WIKI, INDEX = real_wiki, real_index

    # 정리 적용 (AI 응답을 가짜로): 합치기, 없는 대상이면 무시, 순환은 그대로
    from types import SimpleNamespace

    src = {"스킵 연결": "n#t > 1. 스킵 연결", "skip 연결": "n#t > 2. skip 연결", "긍정적 예": "n#t > 4. 네거티브 샘플링",
           "가중치": "n#t > 5. 가중치", "A": "n#t > 6. a", "B": "n#t > 7. b"}
    fake = [Change(name="skip 연결", into="스킵 연결"), Change(name="가중치", into="없는 개념"),
            Change(name="A", into="B"), Change(name="B", into="A")]
    fake_client = SimpleNamespace(messages=SimpleNamespace(parse=lambda **_: SimpleNamespace(
        stop_reason="end_turn", parsed_output=Tidy(changes=fake))))
    tidied, _ = tidy_concepts({n: Concept(name=n, sources=[s]) for n, s in src.items()}, [],
                              [{"id": s, "text": ""} for s in src.values()], fake_client)
    assert sorted(tidied) == ["A", "B", "가중치", "긍정적 예", "스킵 연결"], sorted(tidied)
    assert len(tidied["스킵 연결"].sources) == 2

    chunks, _, _ = load_store()
    done = {s.split("#")[0] for name in load_index() for s in load_page(name).split("## 출처\n")[1].split("- ") if s.strip()}
    notes = sys.argv[1:] or sorted({c["file"] for c in chunks} - done)
    added = build(notes, chunks, anthropic.Anthropic())

    index = load_index()
    ids = {c["id"] for c in chunks}
    for name in index:
        text = load_page(name)
        assert text.startswith(f"# {name}\n"), name
        sources = text.split("## 출처\n")[1].split("\n")
        assert all(s[2:] in ids for s in sources if s), (name, sources)
        related = text.split("## 관련 개념\n")[1].split("\n## 출처")[0].strip().split("\n")
        assert all(r[4:-2] in index for r in related if r), (name, related)

    print(f"노트 {len(notes)}개 → 새 개념 {len(added)}개, 목차 {len(index)}개")
    print(", ".join(added))
    if added:
        print("\n" + load_page(added[0]))
    print("OK")

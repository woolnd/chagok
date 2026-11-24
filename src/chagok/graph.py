"""전체 흐름 (LangGraph): 개념 하나로 검색 → 검색 루프 → 생성 → 근거 루프 → 내 검토에서 멈춤.

흐름 (개념 하나 = thread 하나)
    START
      ▼
    search        find(검색어) → 조각 3개
      ▼
    judge         검색 루프 판단 (retrieve.judge)
      ├─ 충분 ──────────────▶ generate
      ├─ 부족, 시도 남음 ───▶ search (검색어 = 새 검색어)
      ├─ 부족, 시도 끝 ─────▶ END   (노트 부족)
      └─ 개념 아님 ─────────▶ END   (목차에 x)
    generate      문제 만들기 (generate.generate, 위키 페이지·탈락 이유 같이)
      ▼
    check         근거 루프 검사 (check.check)
      ├─ 통과 ──────────────▶ save
      ├─ 탈락, 시도 남음 ───▶ generate (탈락 이유 넣어서)
      └─ 탈락, 시도 끝 ─────▶ END   (버림)
    save          문제를 DB에 "대기"로 저장
      ▼
    review        여기서 멈춤 (interrupt) → 내가 승인/반려하면 이어감 → DB 갱신, 승인이면 목차 날짜
      ▼
    END

밖에서 부르는 함수 (나중에 FastAPI가 그대로 부를 수 있게 셋으로 나눔)
    generate_batch(count)   이번 주 문제 만들기: 개념 count개를 골라 각각 그래프를 돌림 → review에서 멈춤
    pending()               검토 대기 문제 목록 (DB)
    review(qid, ok, reason) 멈춘 그래프를 승인/반려로 이어감

규칙 (기획서 처음 값)
    - 순서가 고정된 흐름, 검사는 검색 뒤와 생성 뒤 두 곳에만
    - 검색 루프·근거 루프 모두 다시 하기 최대 2번
    - 내 검토는 흐름이 멈추고 승인을 기다리는 곳 = 승인율이 측정되는 곳
    - 주말에 한 주 치를 만들고 바로 검토, 평일엔 승인된 문제를 메일로 (mail.py)
    - 멈춘 흐름과 문제 표는 data/chagok.db 하나에 (SQLite)
"""

import sqlite3  # 문제 표 + 멈춘 흐름 저장
from pathlib import Path  # 시험용 임시 DB 경로
from collections.abc import Callable  # find 함수 타입
from datetime import date  # 만든 날·검토한 날
from typing import TypedDict  # State

import anthropic  # Claude API
from langgraph.checkpoint.sqlite import (
    SqliteSaver,
)  # 멈춘 흐름을 파일에 저장 (껐다 켜도 이어감)
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt  # 멈추기 / 이어가기

from chagok.check import MAX_RETRIES as CHECK_RETRIES
from chagok.check import check, feedback
from chagok.generate import Question, generate
from chagok.retrieve import MAX_RETRIES as RETRIEVE_RETRIES
from chagok.retrieve import judge
from chagok.store import ROOT
from chagok.wiki import SKIP, load_index, mark_asked, mark_skipped, wiki_page

DATA = ROOT / "data"
DB = DATA / "chagok.db"

REJECT_REASONS = [
    "근거 없음",
    "애매함",
    "너무 쉬움",
    "중복",
    "기타",
]  # 기획서 반려 사유


class State(TypedDict, total=False):
    """기획서의 State. 무거운 것(모델, 클라이언트)은 넣지 않고 build_graph에 넘긴다."""

    concept: str  # 지금 다루는 개념
    query: str  # 검색어
    chunks: list[dict]  # 찾아온 노트 조각
    page: str  # 위키 개념 페이지 (WIKI_ON이 False면 "")
    question: dict  # 문제 초안 (Question.model_dump(): question, answer, points)
    verdict: dict  # 채점 결과 (Verdict.model_dump())
    feedback: str  # 근거 탈락 이유 → 다시 생성할 때
    search_tries: int  # 검색 다시 한 횟수
    generate_tries: int  # 생성 다시 한 횟수
    result: str  # 끝난 이유: 대기 / 승인 / 반려 / 노트 부족 / 개념 아님 / 버림
    sources: list[str]  # 출처 조각 id (검색 판단에서 관련 있다고 본 것, 메일에 씀)
    thread: str  # 그래프 thread_id = "개념#날짜" (같은 개념이 다른 주에 다시 나와도 섞이지 않게)
    qid: int  # DB 문제 번호 (save 뒤)
    review: dict  # 내 검토 결과 {"ok": bool, "reason": str}
    enough: bool  # 검색 루프: 문제를 만들 만큼 충분한가 (judge_가 채움)
    passed: bool  # 근거 루프: 검사를 통과했나 (check_가 채움)


def open_db() -> sqlite3.Connection:
    """data/chagok.db를 열고 문제 표가 없으면 만든다.

    questions 표
        id INTEGER PRIMARY KEY, thread TEXT (그래프 thread_id = 개념),
        concept, question, answer, points (" / "로 이은 글),
        status TEXT (대기 / 승인 / 반려), reason TEXT (반려 사유),
        created TEXT, reviewed TEXT, sent TEXT (메일 보낸 날, mail.py가 채움),
        sources TEXT (출처 조각 id, 줄바꿈으로 이음. 메일에 "어느 노트 어느 소제목"으로)
    - check_same_thread=False: 그래프 노드(save·review)가 다른 스레드에서 이 연결을 쓰기 때문
    - 멈춘 흐름 저장소(SqliteSaver)는 같은 파일을 연결을 따로 열어 쓴다 (build_graph)
    """
    DATA.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY,
            thread TEXT,
            concept TEXT,
            question TEXT,
            answer TEXT,
            points TEXT,
            status TEXT,
            reason TEXT,
            created TEXT,
            reviewed TEXT,
            sent TEXT,
            sources TEXT
            )
        """)
    # 예전에 만든 DB에는 sources 칸이 없어서 붙여 준다 (CREATE TABLE IF NOT EXISTS는 칸을 안 더함)
    if "sources" not in {row[1] for row in conn.execute("PRAGMA table_info(questions)")}:
        conn.execute("ALTER TABLE questions ADD COLUMN sources TEXT")
    return conn


def build_graph(
    find: Callable[[str], list[dict]],
    examples: list[dict],
    client: anthropic.Anthropic,
    conn: sqlite3.Connection,
):
    """노드를 만들고 이어서 compile한다. 노드는 이 함수 안에서 정의해 find·client·conn을 쓴다.

    - checkpointer=SqliteSaver(같은 파일, 다른 연결): 멈춘 흐름이 DB에 남아 다음 실행에서 이어감
    - 노드 함수는 State를 받아 바꿀 칸만 dict로 돌려준다

    노드 (각각 짧게)
        search(s)    {"chunks": find(s["query"])}
        judge_(s)    retrieve.judge → 개념 아님이면 mark_skipped, result 정하기, 다시 찾을 땐 query·search_tries
        generate_(s) generate(..., feedback=s.get("feedback", ""), page=s["page"]).model_dump()
        check_(s)    check → 탈락이면 feedback·generate_tries, 시도 끝이면 result "버림"
        save(s)      DB에 status "대기"로 넣고 {"qid": ..., "result": "대기"}
        review_(s)   decision = interrupt({...문제...}) → DB 갱신, 승인이면 mark_asked(concept, 오늘)

    조건 간선
        judge 다음: route_judge(s)  → "generate" / "search" / END
        check 다음: route_check(s)  → "save" / "generate" / END

    주의: 이어갈 때 review 노드는 처음부터 다시 실행된다 (interrupt 앞 코드가 두 번 돈다).
         그래서 DB에 넣는 일은 review가 아니라 그 앞의 save 노드에서 한다.
    """

    def search(s: State) -> dict:
        return {"chunks": find(s["query"])}

    def judge_(s: State) -> dict:
        """검색 루프 판단. 끝낼 일이면 result를 채운다 (route_judge가 END로)."""
        j = judge(s["concept"], s["chunks"], client)
        if not j.is_concept:
            mark_skipped(s["concept"])
            return {"enough": False, "result": "개념 아님"}
        if j.enough:
            # 출처: 검색 판단에서 관련 있다고 본 조각만 (없으면 찾은 조각 전부)
            relevant = {c.id for c in j.chunks if c.relevant}
            ids = [ch["id"] for ch in s["chunks"]]
            return {"enough": True, "sources": [i for i in ids if i in relevant] or ids}
        tries = s.get("search_tries", 0)
        if tries >= RETRIEVE_RETRIES:
            return {"enough": False, "result": "노트 부족"}
        # 새 검색어를 비워 보내면 원래 개념으로 (retrieve와 같은 규칙)
        return {
            "enough": False,
            "search_tries": tries + 1,
            "query": j.new_query.strip() or s["concept"],
        }

    def generate_(s: State) -> dict:
        q = generate(
            s["concept"],
            s["chunks"],
            examples,
            client,
            feedback=s.get("feedback", ""),
            page=s.get("page", ""),
        )
        return {"question": q.model_dump()}

    def check_(s: State) -> dict:
        """근거 루프 검사. 탈락이면 이유를 남겨 다시 생성, 시도가 끝났으면 버림."""
        v = check(Question(**s["question"]), s["chunks"], client)
        if v.passed:
            return {"verdict": v.model_dump(), "passed": True}
        tries = s.get("generate_tries", 0)
        if tries >= CHECK_RETRIES:
            return {"verdict": v.model_dump(), "passed": False, "result": "버림"}
        return {
            "verdict": v.model_dump(),
            "passed": False,
            "feedback": feedback(v),
            "generate_tries": tries + 1,
        }

    def save(s: State) -> dict:
        """검사를 통과한 문제를 DB에 "대기"로 넣는다. thread = 이 흐름의 이름표 (review가 이걸로 이어감)."""
        q = s["question"]
        cur = conn.execute(
            "INSERT INTO questions (thread, concept, question, answer, points, status, created, sources) "
            "VALUES (?, ?, ?, ?, ?, '대기', ?, ?)",
            (
                s["thread"],
                s["concept"],
                q["question"],
                q["answer"],
                " / ".join(q["points"]),
                date.today().isoformat(),
                "\n".join(s.get("sources", [])),
            ),
        )
        conn.commit()
        return {"qid": cur.lastrowid, "result": "대기"}

    def review_(s: State) -> dict:
        """여기서 멈춘다. review()가 {"ok", "reason"}으로 이어가면 그 아래가 돈다 (이 함수는 처음부터 다시 실행됨)."""
        decision = interrupt(
            {"qid": s["qid"], "concept": s["concept"], **s["question"]}
        )
        ok, reason, today = (
            decision["ok"],
            decision.get("reason", ""),
            date.today().isoformat(),
        )
        conn.execute(
            "UPDATE questions SET status = ?, reason = ?, reviewed = ? WHERE id = ?",
            ("승인" if ok else "반려", reason, today, s["qid"]),
        )
        conn.commit()
        if (
            ok
        ):  # 승인했을 때만 "마지막으로 문제를 낸 날짜". 반려면 다음 주에 다시 골라질 수 있음
            mark_asked(s["concept"], today)
        return {"review": decision, "result": "승인" if ok else "반려"}

    graph = StateGraph(State)
    graph.add_node("search", search)
    graph.add_node("judge", judge_)
    graph.add_node("generate", generate_)
    graph.add_node("check", check_)
    graph.add_node("save", save)
    graph.add_node("review", review_)

    graph.add_edge(START, "search")
    graph.add_edge("search", "judge")
    graph.add_conditional_edges("judge", route_judge, ["generate", "search", END])
    graph.add_edge("generate", "check")
    graph.add_conditional_edges("check", route_check, ["save", "generate", END])
    graph.add_edge("save", "review")
    graph.add_edge("review", END)

    # 멈춘 흐름 저장소는 연결을 따로 연다 (같은 파일). 문제 표 연결(conn)과 같이 쓰면
    # 저장소가 쓰는 도중에 save·review의 commit이 끼어들어 "cannot commit" 에러가 난다
    return graph.compile(
        checkpointer=SqliteSaver(sqlite3.connect(DB, check_same_thread=False))
    )


def route_judge(state: State) -> str:
    """judge 다음 갈 곳. result가 정해졌으면(노트 부족 / 개념 아님) END, 충분하면 generate, 아니면 search."""
    if state.get("result"):
        return END
    if state.get("enough"):
        return "generate"
    return "search"


def route_check(state: State) -> str:
    """check 다음 갈 곳. 통과면 save, result "버림"이면 END, 아니면 generate."""
    if state.get("passed"):
        return "save"
    if state.get("result"):
        return END
    return "generate"


def generate_batch(count: int, graph, conn: sqlite3.Connection) -> list[dict]:
    """목차에서 오래 안 나온 개념부터 그래프를 돌려 검토 대기 문제를 count개 채운다.

    - 개념 하나 = thread 하나 (thread_id = "개념#오늘 날짜"). 같은 개념이 다른 주에 다시 나와도 섞이지 않게
    - 노트 부족 / 개념 아님 / 버림으로 끝나면 다음 개념으로 넘어가 개수를 채운다
    - 이미 대기 중인 개념(지난번에 만들고 검토 안 한 것)은 다시 만들지 않는다
    출력: 개념마다 끝난 결과 [{"concept": ..., "result": ...}, ...] (터미널에 보여줄 용도)
    """
    index = load_index()
    waiting = {q["concept"] for q in pending(conn)}
    names = sorted(
        (n for n in index if index[n] != SKIP and n not in waiting),
        key=lambda n: index[
            n
        ],  # "-"(한 번도 안 냄) → 오래된 날짜 순 (pick_concept와 같은 기준)
    )

    results, made = [], 0
    for concept in names:
        if made == count:
            break
        thread = f"{concept}#{date.today().isoformat()}"
        out = graph.invoke(
            {
                "concept": concept,
                "query": concept,
                "page": wiki_page(concept),
                "thread": thread,
            },
            {"configurable": {"thread_id": thread}},
        )
        result = (
            "대기" if "__interrupt__" in out else out["result"]
        )  # review에서 멈췄으면 검토 대기
        results.append({"concept": concept, "result": result})
        made += result == "대기"
    return results


def pending(conn: sqlite3.Connection) -> list[dict]:
    """status "대기"인 문제 목록 (오래된 것부터)."""
    rows = conn.execute(
        "SELECT id, concept, question, answer, points FROM questions "
        "WHERE status = '대기' ORDER BY id"
    ).fetchall()

    return [
        {
            "qid": r[0],
            "concept": r[1],
            "question": r[2],
            "answer": r[3],
            "points": r[4].split(" / "),
        }
        for r in rows
    ]


def review(qid: int, ok: bool, reason: str, graph, conn: sqlite3.Connection) -> None:
    """검토 대기 문제 하나를 이어간다: graph.invoke(Command(resume={"ok": ok, "reason": reason}), thread 설정)."""
    thread = conn.execute(
        "SELECT thread FROM questions WHERE id = ?", (qid,)
    ).fetchone()[0]
    graph.invoke(
        Command(resume={"ok": ok, "reason": reason}),
        {"configurable": {"thread_id": thread}},
    )


if __name__ == "__main__":
    # 주말에 돌리는 명령: 이번 주 문제 만들기 → 바로 터미널 검토
    # 실행: uv run --env-file .env python -m chagok.graph [개수, 기본 5]
    #       개수 0이면 만들지 않고 남은 검토 대기만 검토
    import sys
    import tempfile

    import chagok.graph as me

    # 1. API 없이: 가짜 AI로 3개 만들기 → 껐다 켜고 승인·반려 → 대기 하나만 남는지
    real = (
        me.DATA,
        me.DB,
        me.judge,
        me.generate,
        me.check,
        me.mark_asked,
        me.mark_skipped,
        me.load_index,
    )
    from chagok.check import SentenceCheck, Verdict
    from chagok.retrieve import ChunkJudge, Judgment

    me.DATA = Path(tempfile.mkdtemp()) / "data"
    me.DB = me.DATA / "chagok.db"
    me.judge = lambda *_: Judgment(
        chunks=[ChunkJudge(id="a", relevant=True)],
        enough=True,
        missing="",
        new_query="",
        is_concept=_[0] != "점수",  # "점수"는 개념 아님
    )
    me.generate = lambda *_, **__: Question(question="Q", answer="A", points=["p"])
    me.check = lambda *_: Verdict(
        sentences=[SentenceCheck(sentence="x", grounded=True, quote="x")],
        clear=True,
        clear_reason="",
    )
    fake_index = {"퍼셉트론": "2026-11-16", "점수": "-", "XOR 게이트": "-", "GRU": "-", "패딩": "x"}
    asked, skipped = [], []
    me.mark_asked = lambda n, d: (asked.append(n), fake_index.__setitem__(n, d))
    me.mark_skipped = lambda n: (skipped.append(n), fake_index.__setitem__(n, SKIP))
    me.load_index = lambda: dict(fake_index)  # 가짜 목차도 x·날짜가 실제처럼 바뀌게

    conn = me.open_db()
    app = me.build_graph(lambda q: [{"id": "a", "text": "t"}], [], None, conn)
    made = me.generate_batch(2, app, conn)
    assert [(r["concept"], r["result"]) for r in made] == [
        ("점수", "개념 아님"),
        ("XOR 게이트", "대기"),
        ("GRU", "대기"),
    ], made
    assert skipped == ["점수"]
    assert me.generate_batch(1, app, conn) == [
        {"concept": "퍼셉트론", "result": "대기"}
    ]  # 대기 중인 건 다시 안 만듦
    conn.close()
    conn = me.open_db()  # 다른 날 다시 켰다고 치고
    app = me.build_graph(lambda q: [], [], None, conn)
    first, second = [q["qid"] for q in me.pending(conn)][:2]
    me.review(first, True, "", app, conn)
    me.review(second, False, "너무 쉬움", app, conn)
    assert [q["concept"] for q in me.pending(conn)] == ["퍼셉트론"] and asked == [
        "XOR 게이트"
    ]
    assert conn.execute(
        "SELECT status, reason FROM questions WHERE id = ?", (second,)
    ).fetchone() == ("반려", "너무 쉬움")
    conn.close()
    (
        me.DATA,
        me.DB,
        me.judge,
        me.generate,
        me.check,
        me.mark_asked,
        me.mark_skipped,
        me.load_index,
    ) = real

    # 2. 진짜: 이번 주 문제 만들기 → 터미널 검토
    from kiwipiepy import Kiwi
    from sentence_transformers import CrossEncoder, SentenceTransformer

    from chagok.generate import EXAMPLES, load_examples
    from chagok.search import RERANK_MAX_LEN, RERANK_MODEL, load_store, rerank, search
    from chagok.store import EMBED_MODEL

    count = int(sys.argv[1]) if sys.argv[1:] else 5
    conn = me.open_db()
    client = anthropic.Anthropic()
    graph = None
    if count:
        chunks, docs, index = load_store()
        kiwi, model = Kiwi(), SentenceTransformer(EMBED_MODEL)
        reranker = CrossEncoder(RERANK_MODEL, max_length=RERANK_MAX_LEN)

        def find(query: str) -> list[dict]:
            return rerank(
                query, search(query, kiwi, model, chunks, docs, index), reranker
            )

        graph = me.build_graph(find, load_examples(EXAMPLES), client, conn)
        print(f"문제 {count}개 만드는 중...")
        for r in me.generate_batch(count, graph, conn):
            print(f"  {r['concept']}: {r['result']}")
    else:
        graph = me.build_graph(
            lambda q: [], [], client, conn
        )  # 이어가기만: 검색·생성은 안 씀

    todo = me.pending(conn)
    for i, q in enumerate(todo, start=1):
        print(f"\n[{i}/{len(todo)}] {q['concept']}")
        print(f"질문: {q['question']}")
        print(f"모범 답안: {q['answer']}")
        print(f"채점 포인트: {' / '.join(q['points'])}")
        answer = ""
        while answer not in ("a", "r", "s"):
            answer = input("승인(a) / 반려(r) / 나중에(s)? ").strip().lower()
        if answer == "s":
            continue
        reason = ""
        if answer == "r":
            menu = "  ".join(f"{n} {r}" for n, r in enumerate(REJECT_REASONS, start=1))
            pick = input(f"반려 사유: {menu} → ").strip()
            reason = (
                REJECT_REASONS[int(pick) - 1]
                if pick.isdigit() and 1 <= int(pick) <= len(REJECT_REASONS)
                else "기타"
            )
            if reason == "기타":
                reason = "기타: " + input("  자세히: ").strip()
        me.review(q["qid"], answer == "a", reason, graph, conn)

    approved = conn.execute(
        "SELECT COUNT(*) FROM questions WHERE status = '승인' AND sent IS NULL"
    ).fetchone()[0]
    print(f"\n검토 끝. 보낼 승인 문제 {approved}개")

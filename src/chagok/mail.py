"""메일 발송: 평일 아침마다 승인된 문제 하나를 메일로 보낸다. State를 쓰지 않고 따로 돈다.

흐름 (평일 아침 한 번)
    data/chagok.db
      │ next_question   승인 + 아직 안 보낸 문제 중 가장 오래된 것 하나 (없으면 끝)
      │ format_mail     제목, 본문 HTML (TEMPLATE: 질문 → 여백 → 모범 답안·채점 포인트·출처)
      │ send            Resend API로 보내기 (받는 사람은 목록)
      │ mark_sent       보낸 날 기록 → 다음 날엔 다음 문제
      ▼
    메일함

규칙 (기획서 처음 값)
    - 내가 한 번 확인한(승인한) 문제만 나간다
    - 평일 아침마다 하나씩. 요일·시간은 실행하는 쪽(cron)이 정한다. 이 파일은 한 번 실행에 한 통
    - 보내다 실패하면 보낸 날을 기록하지 않는다 → 다음 실행에서 같은 문제를 다시 보냄
    - 지표: 발송 성공률 (발송 기록)

설정 (.env)
    RESEND_API_KEY   Resend API 키
    MAIL_TO          받는 사람, 쉼표로 여러 명. 도메인 인증 전에는 Resend 계정 이메일만 받을 수 있음
"""

import html  # AI가 만든 글을 HTML에 넣기 전에 escape (<eos>, x < y가 깨지지 않게)
import os  # .env 값 읽기
import sqlite3  # 승인된 문제 표
from datetime import date  # 보낸 날

import httpx  # Resend API 요청 (이미 설치돼 있음)

from chagok.graph import open_db

RESEND_URL = "https://api.resend.com/emails"
SENDER = "차곡 <onboarding@resend.dev>"  # 도메인 인증 전에는 이 주소만. 출시 때 내 도메인 주소로

# 메일 HTML 틀. 메일 앱에서 깨지지 않게: 스타일은 태그마다(inline), 레이아웃은 table, JS·웹폰트·아이콘 글꼴·SVG 없음
# 빈칸 (format_mail이 채움, AI가 만든 글은 html.escape 해서):
#   {preheader} 받은편지함 미리보기 줄   {weekday} 요일 한 글자   {date} 예: 11월 25일
#   {concept} 개념   {note} 노트 제목 (출처에서)   {question} 질문   {answer} 모범 답안 (줄바꿈은 <br>)
#   {points} 채점 포인트 <li>들   {sources} 출처 줄들 (<br>로 이음)
TEMPLATE = """<!doctype html>
<html lang="ko">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>차곡</title></head>
<body style="margin:0; padding:0; background-color:#f0f7ff;">
<div style="display:none; max-height:0; overflow:hidden; opacity:0;">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0f7ff;">
<tr><td align="center" style="padding:24px 12px;">

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; background-color:#ffffff; border:1px solid #e0f2fe; border-radius:16px; font-family:-apple-system, BlinkMacSystemFont, 'Apple SD Gothic Neo', Pretendard, 'Malgun Gothic', 'Noto Sans KR', sans-serif;">

  <!-- 위쪽 띠 -->
  <tr><td style="height:6px; font-size:0; line-height:0; background-color:#38bdf8; background-image:linear-gradient(90deg, #bae6fd, #38bdf8, #0284c7); border-radius:16px 16px 0 0;">&nbsp;</td></tr>

  <!-- 머리: 이름 + 배지 + 날짜 -->
  <tr><td style="padding:20px 24px 16px; border-bottom:1px solid #f1f5f9;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="font-size:18px; font-weight:700; color:#0f172a;">
        차곡
        <span style="display:inline-block; margin-left:6px; padding:2px 8px; border-radius:999px; background-color:#e0f2fe; color:#0284c7; font-size:12px; font-weight:600; vertical-align:middle;">{weekday}요 모닝 레터</span>
      </td>
      <td align="right" style="font-size:13px; color:#64748b; white-space:nowrap;">{date}</td>
    </tr></table>
  </td></tr>

  <!-- 태그: 개념 + 노트 -->
  <tr><td style="padding:20px 24px 0;">
    <span style="display:inline-block; margin:0 6px 6px 0; padding:4px 10px; border-radius:8px; background-color:#e0f2fe; color:#0369a1; font-size:12px; font-weight:700;">{concept}</span>
    <span style="display:inline-block; margin:0 6px 6px 0; padding:4px 10px; border-radius:8px; background-color:#f8fafc; border:1px solid #e2e8f0; color:#64748b; font-size:12px;">{note}</span>
  </td></tr>

  <!-- 안내 -->
  <tr><td style="padding:14px 24px 0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="padding:14px 16px; background-color:#f0f9ff; border:1px solid #bae6fd; border-radius:12px; font-size:14px; line-height:1.6; color:#334155;">
        출근길이나 커피를 기다리며, 아래 질문의 답을 1분간 머릿속으로 떠올려 보세요.
      </td>
    </tr></table>
  </td></tr>

  <!-- 질문 -->
  <tr><td style="padding:24px 24px 0;">
    <p style="margin:0 0 10px; font-size:12px; font-weight:700; letter-spacing:0.5px; color:#0284c7;">● 오늘의 질문</p>
    <p style="margin:0; font-size:21px; font-weight:700; line-height:1.55; color:#0f172a;">{question}</p>
  </td></tr>

  <!-- 답이 바로 보이지 않게 하는 여백 -->
  <tr><td align="center" style="padding:56px 24px 240px; font-size:13px; color:#94a3b8;">
    ↓ 생각을 정리한 뒤 내려서 답 확인
  </td></tr>

  <!-- 모범 답안 -->
  <tr><td style="padding:0 24px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="padding:18px; background-color:#f8fbff; border:1px solid #e0f2fe; border-radius:12px;">
        <p style="margin:0 0 10px; font-size:14px; font-weight:700; color:#0f172a;">💡 모범 답안</p>
        <p style="margin:0; font-size:15px; line-height:1.75; color:#334155;">{answer}</p>
      </td>
    </tr></table>
  </td></tr>

  <!-- 채점 포인트 -->
  <tr><td style="padding:12px 24px 0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="padding:14px 16px; background-color:#fff7ed; border:1px solid #ffedd5; border-radius:12px;">
        <p style="margin:0 0 6px; font-size:12px; font-weight:700; color:#c2410c;">채점 포인트</p>
        <ul style="margin:0; padding-left:18px; font-size:14px; line-height:1.7; color:#7c2d12;">{points}</ul>
      </td>
    </tr></table>
  </td></tr>

  <!-- 출처 -->
  <tr><td style="padding:16px 24px 0; font-size:12px; line-height:1.6; color:#64748b;">
    <span style="font-weight:700; color:#475569;">출처</span><br>{sources}
  </td></tr>

  <!-- 바닥글 (구독형 출시 때 수신 거부 링크 자리) -->
  <tr><td style="padding:20px 24px 24px; margin-top:20px; font-size:12px; line-height:1.6; color:#94a3b8; text-align:center;">
    <div style="border-top:1px solid #f1f5f9; padding-top:16px;">주말에 직접 확인한 문제만 보냅니다 · 차곡</div>
  </td></tr>

</table>

</td></tr>
</table>
</body>
</html>
"""


def next_question(conn: sqlite3.Connection) -> dict | None:
    """status "승인"이고 sent가 비어 있는 문제 중 가장 오래된 것(검토한 날 → id 순) 하나. 없으면 None.

    출력: {"qid", "concept", "question", "answer", "points"(리스트), "sources"(리스트)}
      - points는 " / ", sources는 줄바꿈으로 이어 저장돼 있음 → 다시 리스트로
    """
    row = conn.execute(
        "SELECT id, concept, question, answer, points, sources FROM questions "
        "WHERE status = '승인' AND sent IS NULL "
        "ORDER BY reviewed, id LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return {
        "qid": row[0],
        "concept": row[1],
        "question": row[2],
        "answer": row[3],
        "points": row[4].split(" / "),
        "sources": [s for s in (row[5] or "").split("\n") if s],
    }


def source_label(chunk_id: str) -> str:
    """조각 id → 메일에 보여줄 출처 한 줄.

    예: "2026-11-09_gated_rnn.md#게이트가 추가된 RNN > 2. 기울기 소실과 기울기 폭발의 원인"
      → "게이트가 추가된 RNN > 2. 기울기 소실과 기울기 폭발의 원인 (2026-11-09_gated_rnn.md)"
    """
    file, _, rest = chunk_id.partition("#")
    return f"{rest} ({file})"


def format_mail(q: dict) -> tuple[str, str]:
    """문제 하나 → (제목, 본문 HTML). TEMPLATE의 빈칸을 채운다.

    - 제목: "[차곡] 오늘의 복습 · {개념}"
    - AI가 만든 글(질문, 답안, 포인트, 출처)은 html.escape 한 뒤 넣는다 (<eos>, x < y 같은 글자가 깨지지 않게)
    - answer: escape 한 뒤 줄바꿈을 <br>로
    - points: "<li>포인트</li>"를 이어 붙임
    - sources: source_label 한 줄씩, "<br>"로 이음
    - note: 첫 출처 id의 노트 제목 ("파일#제목 > 소제목"에서 "제목")
    - weekday: "월화수목금토일"[오늘.weekday()], date: f"{월}월 {일}일"
    - preheader: f"오늘의 복습 · {개념}" (받은편지함 목록에 답이 새지 않게)
    """
    e = html.escape
    today = date.today()

    subject = f"[차곡] 오늘의 복습 · {q['concept']}"
    # 노트 제목: 첫 출처 "파일#제목 > 소제목"에서 "제목" (출처가 없으면 빈 글자)
    note = q["sources"][0].partition("#")[2].partition(" > ")[0] if q["sources"] else ""
    body = TEMPLATE.format(
        preheader=e(f"오늘의 복습 · {q['concept']}"),
        weekday="월화수목금토일"[today.weekday()],
        date=f"{today.month}월 {today.day}일",
        concept=e(q["concept"]),
        note=e(note),
        question=e(q["question"]),
        answer=e(q["answer"]).replace("\n", "<br>"),
        points="".join(f"<li>{e(p)}</li>" for p in q["points"]),
        sources="<br>".join(e(source_label(s)) for s in q["sources"]),
    )
    return subject, body


def send(to: list[str], subject: str, body: str) -> str:
    """Resend로 한 통 보내고 메일 id를 돌려준다. 실패하면 에러로 멈춘다 (보낸 날을 기록하지 않게).

    - POST RESEND_URL, 헤더 Authorization: Bearer {RESEND_API_KEY}
    - JSON {"from": SENDER, "to": to, "subject": subject, "html": body} (글자 버전은 Resend가 자동으로 만듦)
    - 성공: {"id": "..."}. 실패(401 키 틀림, 403 받는 사람 제한 등)는 response.raise_for_status()로 멈춤
    - ponytail: 출시(구독자 여러 명) 때는 이 함수만 바꾸면 됨 (보내는 주소, 묶어 보내기)
    """
    response = httpx.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"},
        json={"from": SENDER, "to": to, "subject": subject, "html": body},
    )
    response.raise_for_status()
    return response.json()["id"]


def mark_sent(conn: sqlite3.Connection, qid: int) -> None:
    """보낸 문제의 sent를 오늘 날짜로."""
    conn.execute(
        "UPDATE questions SET sent = ? WHERE id = ?", (date.today().isoformat(), qid)
    )
    conn.commit()


if __name__ == "__main__":
    # 평일 아침에 한 번 (cron)
    # 실행: uv run --env-file .env python -m chagok.mail          다음 문제 하나 보내기
    #       uv run --env-file .env python -m chagok.mail --test   예시 문제로 시험 발송 (DB는 건드리지 않음)
    import sys
    import tempfile
    from pathlib import Path

    import chagok.graph as graph

    # 1. API 없이: 임시 DB로 순서·기록, format_mail 모양
    real_data, real_db = graph.DATA, graph.DB
    graph.DATA = Path(tempfile.mkdtemp()) / "data"
    graph.DB = graph.DATA / "chagok.db"
    conn = open_db()
    assert next_question(conn) is None  # 보낼 게 없으면 None
    for concept, status, reviewed in [("A", "승인", "2026-11-23"), ("B", "대기", None), ("C", "승인", "2026-11-22")]:
        conn.execute(
            "INSERT INTO questions (concept, question, answer, points, status, reviewed, sources) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (concept, "x < y?", "첫 줄\n둘째 줄", "p1 / p2", status, reviewed, "n.md#노트 > 1. 소제목"),
        )
    q = next_question(conn)
    assert q["concept"] == "C" and q["points"] == ["p1", "p2"]  # 먼저 승인한 것부터
    subject, body = format_mail(q)
    assert subject == "[차곡] 오늘의 복습 · C"
    assert "x &lt; y?" in body and "첫 줄<br>둘째 줄" in body and "1. 소제목 (n.md)" in body and ">노트</span>" in body
    mark_sent(conn, q["qid"])
    assert next_question(conn)["concept"] == "A"  # 보낸 건 다시 안 나옴
    conn.close()
    graph.DATA, graph.DB = real_data, real_db

    # 2. 진짜 보내기
    to = [a.strip() for a in os.environ["MAIL_TO"].split(",") if a.strip()]
    if "--test" in sys.argv:
        q = {
            "qid": 0,
            "concept": "기울기 소실",
            "question": "RNN에서 시간 방향으로 역전파될 때 기울기 소실이 일어나는 원인을 tanh 노드와 MatMul 노드의 역할을 중심으로 설명하시오.",
            "answer": "tanh 노드의 미분 1 − y²은 최대 1.0이므로, 기울기가 tanh 노드를 지날 때마다 1 이하의 값이 곱해져 작아진다.\n"
                      "MatMul 노드에서는 매번 똑같은 가중치 W_h가 곱해지므로, W_h의 특잇값 최댓값이 1보다 작으면 기울기가 지수적으로 감소한다.",
            "points": ["tanh 노드: 미분 1 − y²은 최대 1", "MatMul 노드: 같은 W_h를 반복 곱해 지수적으로 감소"],
            "sources": ["2026-11-09_gated_rnn.md#게이트가 추가된 RNN > 2. 기울기 소실과 기울기 폭발의 원인"],
        }
        subject, body = format_mail(q)
        print(f"시험 발송: {send(to, '[시험] ' + subject, body)} → 받는 사람 {len(to)}명")
        sys.exit()

    conn = open_db()
    q = next_question(conn)
    if q is None:
        print("보낼 승인 문제가 없음. 주말에 문제를 만들고 검토하세요 (python -m chagok.graph)")
        sys.exit()
    subject, body = format_mail(q)
    mail_id = send(to, subject, body)  # 실패하면 여기서 멈춤 → mark_sent 안 함 → 다음 실행에서 다시
    mark_sent(conn, q["qid"])
    left = conn.execute("SELECT COUNT(*) FROM questions WHERE status = '승인' AND sent IS NULL").fetchone()[0]
    print(f"보냄: {q['concept']} (메일 {mail_id}) → 받는 사람 {len(to)}명, 남은 승인 문제 {left}개")

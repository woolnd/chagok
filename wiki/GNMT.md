# GNMT

## 정의
구글 번역은 2016년부터 신경망 번역인 GNMT(Google Neural Machine Translation)를 사용한다.

## 핵심 포인트
- GNMT는 어텐션을 갖춘 seq2seq처럼 Encoder, Decoder, Attention으로 구성된다.
- GNMT는 LSTM 계층 8층 다층화, Encoder 첫 번째 계층의 양방향 LSTM, skip 연결, 다수 GPU 분산 학습 등 개선을 더해 번역 정확도를 높였다.
- GNMT는 기존 구문 기반 기계 번역(PBMT)보다 번역 품질을 크게 끌어올려 사람의 번역에 가까워졌지만, 대량의 학습 데이터와 많은 컴퓨팅 자원이 필요하다.

## 관련 개념
- [[신경망 기계 번역]]
- [[seq2seq]]
- [[Encoder-Decoder 모델]]
- [[Encoder]]
- [[Decoder]]
- [[어텐션]]
- [[양방향 LSTM]]

## 출처
- 2026-11-17_attention.md#어텐션 > 11. 구글 신경망 기계 번역(GNMT)

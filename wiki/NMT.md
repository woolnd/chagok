# NMT

## 정의
문장 전체를 신경망으로 번역하는 신경망 기계 번역(NMT, Neural Machine Translation)이 주류다. NMT는 처음에는 통계 기반 번역과 대비되는 말로 쓰였지만, 지금은 seq2seq를 사용한 기계 번역의 총칭으로 쓰인다.

## 핵심 포인트
- NMT는 처음에 통계 기반 번역과 대비되는 말로 쓰였고, 지금은 seq2seq를 사용한 기계 번역의 총칭이다.
- 구글 번역은 2016년부터 NMT의 한 형태인 GNMT를 사용한다.
- GNMT는 Encoder, Decoder, Attention으로 구성되며 8층 LSTM 다층화, Encoder 첫 계층 양방향 LSTM, skip 연결, 다수 GPU 분산 학습 등이 더해졌다.
- NMT(GNMT)는 대량의 학습 데이터와 많은 컴퓨팅 자원이 필요하다는 한계가 있다.

## 관련 개념
- [[seq2seq]]
- [[Encoder]]
- [[Decoder]]
- [[어텐션]]
- [[LSTM]]
- [[양방향 LSTM]]
- [[skip 연결]]
- [[GNMT]]
- [[PBMT]]
- [[통계 기반 기법]]

## 출처
- 2026-11-17_attention.md#어텐션 > 11. 구글 신경망 기계 번역(GNMT)

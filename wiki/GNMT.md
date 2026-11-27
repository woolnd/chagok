# GNMT

## 정의
GNMT(Google Neural Machine Translation)는 2016년부터 구글 번역이 사용하는 신경망 번역이다.

## 핵심 포인트
- GNMT도 어텐션을 갖춘 seq2seq처럼 Encoder, Decoder, Attention으로 구성된다.
- LSTM 계층을 8층으로 다층화하고, Encoder의 첫 번째 계층에만 양방향 LSTM을 쓰며, skip 연결을 적용한다.
- 다수의 GPU로 분산 학습하여 학습 시간을 단축하고, 기존 구문 기반 기계 번역(PBMT)보다 번역 품질을 크게 끌어올렸다.

## 관련 개념
- [[seq2seq]]
- [[NMT]]
- [[PBMT]]
- [[어텐션]]
- [[Encoder]]
- [[Decoder]]
- [[Attention 계층]]
- [[양방향 LSTM]]
- [[skip 연결]]

## 출처
- 2026-11-17_attention.md#어텐션 > 11. 구글 신경망 기계 번역(GNMT)

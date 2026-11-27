# seq2seq

## 정의
seq2seq(sequence to sequence)는 시계열 데이터를 다른 시계열 데이터로 변환하는 모델로, 2개의 RNN을 이용한다. Encoder-Decoder 모델이라고도 한다.

## 핵심 포인트
- Encoder는 입력 시계열을 고정 길이 은닉 상태 벡터 h로 인코딩하고, Decoder는 h를 조건으로 받아 출력을 디코딩한다.
- <eos>는 Decoder에 문장 생성의 시작을 알리는 구분자이자, Decoder가 출력하면 생성을 멈추는 종료 신호다.
- Encoder의 고정 길이 벡터 h에 모든 정보를 담아야 하므로 문장이 길어질수록 정보가 부족해지는 문제가 있으며, 이를 해결하는 방법이 어텐션이다.

## 관련 개념
- [[시계열 데이터]]
- [[LSTM]]
- [[GRU]]
- [[Encoder]]
- [[Decoder]]
- [[<eos>]]
- [[은닉 상태]]
- [[언어 모델]]
- [[어텐션]]

## 출처
- 2026-11-11_rnn_text_generation.md#RNN을 사용한 문장 생성 > 2. seq2seq
- 2026-11-17_attention.md#어텐션 > 1. seq2seq의 문제점

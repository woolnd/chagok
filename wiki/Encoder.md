# Encoder

## 정의
Encoder는 RNN을 이용해 시계열 데이터를 h라는 은닉 상태 벡터(hidden state vector)로 변환한다.

## 핵심 포인트
- Encoder는 입력 시계열을 LSTM 마지막 은닉 상태 h로 변환하며, 이 h에 입력 문장을 번역하는 데 필요한 정보가 인코딩된다.
- h는 고정 길이 벡터이므로 입력 문장의 길이와 관계없이 크기가 같다.
- Encoder가 넘기는 정보는 h 하나뿐이며, Decoder LSTM의 초기 은닉 상태로 설정되고 기억 셀은 넘기지 않는다.

## 관련 개념
- [[seq2seq]]
- [[Decoder]]
- [[LSTM]]
- [[은닉 상태]]
- [[Embedding 계층]]
- [[GRU]]

## 출처
- 2026-11-11_rnn_text_generation.md#RNN을 사용한 문장 생성 > 2. seq2seq
- 2026-11-11_rnn_text_generation.md#RNN을 사용한 문장 생성 > 4. seq2seq 구현

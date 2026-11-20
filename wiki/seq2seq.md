# seq2seq

## 정의
seq2seq(sequence to sequence)는 2개의 RNN을 이용해 시계열 데이터를 다른 시계열 데이터로 변환하는 모델이다. Encoder-Decoder 모델이라고도 한다.

## 핵심 포인트
- Encoder는 입력 데이터를 인코딩하고 마지막 은닉 상태 h를 Decoder로 넘기며, Decoder는 h를 받아 인코딩된 데이터를 디코딩한다.
- h는 고정 길이 벡터이므로 입력 문장이 길어질수록 필요한 정보가 다 담기지 못하는 문제가 있다.
- 학습 시에는 교사 강요로 정답 단어를 입력하고, 생성 시에는 <eos>를 시작 신호로 주고 출력 단어를 다음 입력으로 반복한다.

## 관련 개념
- [[Encoder]]
- [[Decoder]]
- [[<eos>]]
- [[LSTM]]
- [[교사 강요]]
- [[어텐션]]
- [[RNN 계층]]
- [[Time 계층]]
- [[Encoder-Decoder 모델]]
- [[은닉 상태]]
- [[맥락 벡터]]
- [[Embedding 계층]]

## 출처
- 2026-11-11_rnn_text_generation.md#RNN을 사용한 문장 생성 > 2. seq2seq
- 2026-11-11_rnn_text_generation.md#RNN을 사용한 문장 생성 > 4. seq2seq 구현
- 2026-11-17_attention.md#어텐션 > 1. seq2seq의 문제점
- 2026-11-17_attention.md#어텐션 > 2. Encoder 개선
- 2026-11-17_attention.md#어텐션 > 3. Decoder 개선 ①: 선택을 가중합으로
- 2026-11-17_attention.md#어텐션 > 5. Decoder 개선 ③: Attention 계층

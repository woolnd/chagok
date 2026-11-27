# <eos>

## 정의
seq2seq(sequence to sequence)는 2개의 RNN을 이용해 시계열 데이터를 다른 시계열 데이터로 변환하는 모델이다. Encoder-Decoder 모델이라고도 한다.

## 핵심 포인트
- Encoder는 입력 시계열을 고정 길이 은닉 상태 벡터 h로 인코딩하고, Decoder는 h를 받아 출력 시계열을 디코딩한다.
- Decoder는 언어 모델(Embedding → LSTM → Affine → Softmax)과 같은 구성이며, LSTM이 벡터 h를 입력받는다는 점만 다르다.
- <eos>는 Decoder의 생성 시작 신호이자 종료 신호인 구분자다.
- LSTM의 은닉 상태 h가 Encoder와 Decoder를 잇는 가교가 되며, 역전파 때 기울기가 Decoder에서 Encoder로 전해져 두 LSTM을 한 번에 학습한다.

## 관련 개념
- [[Encoder]]
- [[Decoder]]
- [[시계열 데이터]]
- [[Embedding 계층]]
- [[LSTM]]
- [[GRU]]
- [[RNN 언어 모델]]
- [[언어 모델]]
- [[순환 신경망]]
- [[은닉 상태]]

## 출처
- 2026-11-11_rnn_text_generation.md#RNN을 사용한 문장 생성 > 2. seq2seq

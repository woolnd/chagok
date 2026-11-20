# Encoder-Decoder 모델

## 정의
seq2seq를 Encoder-Decoder 모델이라고도 한다. Encoder는 입력 데이터를 인코딩(부호화)하고, Decoder는 인코딩된 데이터를 디코딩(복호화)한다.

## 핵심 포인트
- Encoder는 RNN(예: LSTM)으로 시계열 데이터를 은닉 상태 벡터 h로 변환하며, h는 입력 길이와 무관한 고정 길이 벡터다
- Decoder는 h라는 조건이 주어진 언어 모델이며, 첫 LSTM 계층이 Encoder의 h를 입력받는다는 점이 일반 언어 모델과의 차이다
- <eos>는 Decoder에 문장 생성의 시작을 알리고, Decoder가 출력하면 생성을 멈추는 종료 신호로 쓰인다

## 관련 개념
- [[seq2seq]]
- [[Encoder]]
- [[Decoder]]
- [[<eos>]]
- [[LSTM]]
- [[RNN 계층]]
- [[은닉 상태]]
- [[시계열 데이터]]
- [[인코딩]]
- [[디코딩]]
- [[가변 길이 시계열 데이터]]
- [[언어 모델]]
- [[역전파]]

## 출처
- 2026-11-11_rnn_text_generation.md#RNN을 사용한 문장 생성 > 2. seq2seq

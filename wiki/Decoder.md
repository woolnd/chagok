# Decoder

## 정의
Decoder는 앞 장의 언어 모델 신경망(Embedding → LSTM → Affine → Softmax)과 완전히 같은 구성이다. 단 한 가지만 다른데, 바로 LSTM 계층이 벡터 h를 입력받는다는 점이다.

## 핵심 포인트
- Decoder는 "h라는 조건이 주어진 언어 모델"이다. LSTM 계층이 Encoder의 h를 초기 은닉 상태로 받는다는 점이 언어 모델과의 차이다.
- <eos>는 Decoder에 문장 생성의 시작을 알리는 신호이자, Decoder가 출력하면 생성을 멈추는 종료 신호다.
- Decoder 클래스는 Time Embedding → Time LSTM → Time Affine 순으로 쌓으며, 매 시각 입력되는 단어 ID는 Embedding으로 벡터화하고 h는 Embedding을 거치지 않는다.
- 기억 셀은 Encoder에서 넘기지 않으므로 Decoder의 기억 셀은 0에서 시작하며, Encoder와 Decoder 사이를 오가는 정보는 h 하나뿐이다.

## 관련 개념
- [[Encoder]]
- [[seq2seq]]
- [[Encoder-Decoder 모델]]
- [[<eos>]]
- [[언어 모델]]
- [[은닉 상태]]
- [[Embedding 계층]]
- [[교사 강요]]
- [[확률적 선택]]
- [[샘플링]]
- [[결정적 선택]]
- [[기억 셀]]
- [[RNN 언어 모델]]
- [[시계열 데이터]]

## 출처
- 2026-11-11_rnn_text_generation.md#RNN을 사용한 문장 생성 > 2. seq2seq
- 2026-11-11_rnn_text_generation.md#RNN을 사용한 문장 생성 > 4. seq2seq 구현

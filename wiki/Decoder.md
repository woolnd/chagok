# Decoder

## 정의
Decoder는 Encoder가 출력한 h를 받아 목적으로 하는 다른 문자열을 출력하는 부분이다. 앞 장의 언어 모델 신경망(Embedding → LSTM → Affine → Softmax)과 완전히 같은 구성이며, LSTM 계층이 벡터 h를 입력받는다는 점만 다르다. 즉 Decoder는 "h라는 조건이 주어진 언어 모델"이다.

## 핵심 포인트
- Decoder는 Time Embedding → Time LSTM → Time Affine 순으로 쌓는다.
- Encoder가 넘긴 h는 Decoder LSTM의 초기 은닉 상태로 설정되고, 기억 셀은 넘기지 않아 0에서 시작한다.
- Decoder의 Time Embedding은 h가 아니라 매 시각 입력되는 단어 ID를 처리하며, h는 이미 벡터이므로 Embedding을 거치지 않는다.
- 학습 시에는 정답 단어를 입력하는 교사 강요를 쓰고, 생성 시에는 <eos>로 시작해 출력 단어를 다음 입력으로 반복한다.
- <eos>는 Decoder에 문장 생성의 시작을 알리는 신호이며, Decoder가 <eos>를 출력하면 생성을 멈춘다.

## 관련 개념
- [[Encoder]]
- [[seq2seq]]
- [[<eos>]]
- [[교사 강요]]
- [[은닉 상태]]
- [[LSTM]]
- [[Embedding 계층]]
- [[언어 모델]]
- [[샘플링]]

## 출처
- 2026-11-11_rnn_text_generation.md#RNN을 사용한 문장 생성 > 2. seq2seq
- 2026-11-11_rnn_text_generation.md#RNN을 사용한 문장 생성 > 4. seq2seq 구현

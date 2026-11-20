# <eos>

## 정의
<eos>(end of sentence)라는 구분 기호(특수 문자)는 Decoder에 문장 생성의 시작을 알리는 신호로 이용된다. Decoder가 <eos>를 출력하면 생성을 멈추므로 종료 신호이기도 하다.

## 핵심 포인트
- <eos>는 Decoder에 시작과 종료를 알리는 구분자이다.
- Decoder의 입력은 <eos>로 시작하고, 출력은 문장 끝에 <eos>로 끝난다.
- Decoder가 <eos>를 출력하면 문장 생성을 멈춘다.

## 관련 개념
- [[seq2seq]]
- [[Encoder]]
- [[Decoder]]
- [[Encoder-Decoder 모델]]

## 출처
- 2026-11-11_rnn_text_generation.md#RNN을 사용한 문장 생성 > 2. seq2seq

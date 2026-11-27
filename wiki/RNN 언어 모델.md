# RNN 언어 모델

## 정의
RNN 언어 모델(RNNLM, RNN Language Model)은 Time Embedding → Time RNN → Time Affine → Time Softmax with Loss 순서로 쌓은 언어 모델이다.

## 핵심 포인트
- 기존 계층에 시간 축을 추가한 Time 계층은 (N, T, …) 형태의 T개 시각 데이터 묶음을 처리한다
- Time Embedding, Time RNN, Time Affine은 시각별로 처리하며 가중치는 모든 시각이 공유한다
- Time RNN만 이전 시각의 은닉 상태를 이어받아 시각 순서대로 처리해야 하고, Time Embedding과 Time Affine은 T개 시각을 한 번에 계산할 수 있다
- Time Softmax with Loss는 시각별 손실을 구한 뒤 더해 T로 나눈 평균을 최종 손실로 사용하며, 출력(확률)은 더하지 않고 손실만 평균한다

## 관련 개념
- [[순환 신경망]]
- [[시계열 데이터]]
- [[언어 모델]]
- [[Time 계층]]
- [[은닉 상태]]
- [[Embedding 계층]]
- [[Attention 계층]]
- [[BPTT]]
- [[Truncated BPTT]]
- [[소프트맥스 함수]]
- [[손실 함수]]
- [[교차 엔트로피 오차]]
- [[퍼플렉서티]]
- [[LSTM]]
- [[GRU]]

## 출처
- 2026-11-05_rnn.md#순환 신경망(RNN) > 6. Time 계층

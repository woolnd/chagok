# RNN 언어 모델

## 정의
시계열 데이터를 처리하기 위해 기존 계층(Embedding, RNN, Affine, Softmax with Loss)에 시간 축을 추가해 T개 시각의 데이터 묶음 (N, T, …)을 한꺼번에 받아 처리하도록 확장한 계층. RNN 언어 모델은 Time Embedding → Time RNN → Time Affine → Time Softmax with Loss 순서로 쌓는다.

## 핵심 포인트
- Time Embedding, Time RNN, Time Affine은 시각별로 처리하며 각 계층의 가중치는 모든 시각이 공유한다.
- Time RNN만 이전 시각의 은닉 상태를 이어받아 시각 순서대로 처리하고, Time Embedding과 Time Affine은 T개 시각을 한 번에 계산할 수 있다.
- Time Softmax with Loss는 시각마다 소프트맥스와 손실을 따로 구한 뒤 손실들의 합을 T로 나눈 평균을 최종 손실로 쓴다. 출력(확률)은 더하지 않고 손실만 평균낸다.

## 관련 개념
- [[RNN 계층]]
- [[은닉 상태]]
- [[시계열 데이터]]
- [[Embedding 계층]]
- [[Time 계층]]
- [[미니배치]]
- [[손실 함수]]
- [[소프트맥스 함수]]
- [[가중치 공유]]
- [[순환 신경망]]
- [[언어 모델]]

## 출처
- 2026-11-05_rnn.md#순환 신경망(RNN) > 6. Time 계층

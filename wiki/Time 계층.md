# Time 계층

## 정의
기존 계층(Embedding, RNN, Affine, Softmax with Loss)에 시간 축을 추가해 T개 시각의 데이터 묶음 (N, T, …)을 받아 처리하도록 확장한 계층

## 핵심 포인트
- 기존 계층과 계산 원리는 같고, 입력이 T개 시각의 묶음 (N, T, …)이라는 점이 다르다 (N: 미니배치 크기, T: 시각 수, H: 은닉 상태 벡터 크기)
- Time Embedding, Time RNN, Time Affine은 시각별로 처리하며 모든 시각이 가중치를 공유한다
- Time RNN만 이전 시각의 은닉 상태를 이어받아 시각 순서대로 처리해야 하고, Time Embedding과 Time Affine은 T개 시각을 한 번에 계산할 수 있다
- Time Softmax with Loss는 시각마다 손실을 구한 뒤 평균(합을 T로 나눔)을 최종 손실로 쓰며, 출력 확률은 더하지 않고 손실만 평균한다

## 관련 개념
- [[RNN 언어 모델]]
- [[순환 신경망]]
- [[Embedding 계층]]
- [[은닉 상태]]
- [[시계열 데이터]]
- [[BPTT]]
- [[Truncated BPTT]]
- [[미니배치]]
- [[배치 크기]]
- [[손실 함수]]
- [[교차 엔트로피 오차]]

## 출처
- 2026-11-05_rnn.md#순환 신경망(RNN) > 6. Time 계층

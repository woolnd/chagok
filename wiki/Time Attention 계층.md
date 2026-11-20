# Time Attention 계층

## 정의
여러 시각의 Attention 계층을 한꺼번에 처리하도록 묶은 것이 Time Attention 계층이다. 각 시각의 Attention 계층은 같은 hs를 받고, 그 시각의 h만 다르다.

## 핵심 포인트
- Attention 계층은 Attention Weight(내적 유사도 s → softmax로 가중치 a)와 Weight Sum(가중치로 hs를 가중합해 맥락 벡터 c 생성) 두 단계로 계산한다.
- Time Attention 계층은 Decoder의 LSTM 계층과 Affine 계층 사이에 들어가며, 각 시각마다 맥락 벡터 c를 만들고 c와 h를 연결해 Affine 계층에 입력한다.
- Attention 계층을 LSTM 다음 시각 입력으로 넣는 구성도 가능하지만, Decoder 데이터 흐름이 한 방향이라 LSTM과 Affine 사이에 넣는 구성이 모듈화하기 쉽다.

## 관련 개념
- [[어텐션]]
- [[맥락 벡터]]
- [[내적]]
- [[소프트맥스 함수]]
- [[Encoder]]
- [[Decoder]]
- [[seq2seq]]
- [[LSTM]]
- [[은닉 상태]]
- [[Time 계층]]

## 출처
- 2026-11-17_attention.md#어텐션 > 5. Decoder 개선 ③: Attention 계층
- 2026-11-17_attention.md#어텐션 > 9. Attention 계층 사용 방법

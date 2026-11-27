# Attention 계층

## 정의
Attention 계층은 Encoder가 출력한 각 단어의 벡터 hs와 Decoder LSTM의 은닉 상태 h를 내적해 유사도 점수 s를 구하고, 소프트맥스로 정규화해 가중치 a를 얻은 뒤, 그 가중치로 hs를 가중합해 맥락 벡터 c를 만드는 계층이다.

## 핵심 포인트
- 두 단계 계산: Attention Weight 계층(내적 → 소프트맥스로 가중치 a)과 Weight Sum 계층(가중합으로 맥락 벡터 c)
- Attention 계층은 Decoder의 LSTM 계층과 Affine 계층 사이에 들어가며, c와 LSTM의 은닉 상태 h를 연결해 Affine 계층에 입력한다
- 여러 시각의 Attention 계층을 묶은 것이 Time Attention 계층이며, 각 시각은 같은 hs를 받고 그 시각의 h만 다르다
- 입력 전체를 고정 길이 벡터 하나에 압축하던 seq2seq의 한계를, 매 시각 필요한 입력 정보를 새로 꺼내 쓰는 방식으로 해결했다

## 관련 개념
- [[어텐션]]
- [[얼라인먼트]]
- [[가중치 a]]
- [[맥락 벡터]]
- [[가중합]]
- [[점수]]
- [[Attention Weight 계층]]
- [[Weight Sum 계층]]
- [[Time Attention 계층]]
- [[seq2seq]]
- [[Encoder]]
- [[Decoder]]
- [[은닉 상태]]
- [[소프트맥스 함수]]

## 출처
- 2026-11-17_attention.md#어텐션 > 5. Decoder 개선 ③: Attention 계층

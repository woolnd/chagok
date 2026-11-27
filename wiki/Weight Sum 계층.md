# Weight Sum 계층

## 정의
Attention Weight 계층이 구한 가중치 a의 비율대로 hs의 단어 벡터들을 실제로 가중합해, 지금 필요한 입력 정보를 담은 맥락 벡터 c를 만드는 계층이다.

## 핵심 포인트
- c = Σᵢ aᵢ hsᵢ 로 계산하며, 가중치 a의 비율대로 hs의 단어 벡터들을 가중합한다.
- 두 단계 계산 중 두 번째 단계이며, Attention Weight 계층(s = h·hs, a = softmax(s))의 결과를 입력으로 받는다.
- 각 시각마다 맥락 벡터 c를 만들어 은닉 상태 h와 연결한 뒤 Affine 계층에 입력한다.

## 관련 개념
- [[Attention Weight 계층]]
- [[Attention 계층]]
- [[Time Attention 계층]]
- [[맥락 벡터]]
- [[가중합]]
- [[가중치 a]]
- [[어텐션]]
- [[seq2seq]]
- [[소프트맥스 함수]]
- [[Encoder]]
- [[Decoder]]

## 출처
- 2026-11-17_attention.md#어텐션 > 5. Decoder 개선 ③: Attention 계층

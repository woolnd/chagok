# Time Attention 계층

## 정의
여러 시각의 Attention 계층을 한꺼번에 처리하도록 묶은 것이 Time Attention 계층이다. 각 시각의 Attention 계층은 같은 hs를 받고, 그 시각의 h만 다르다.

## 핵심 포인트
- 각 시각의 Attention 계층은 같은 hs를 받고 그 시각의 h만 다르다
- Attention 계층은 Attention Weight 계층(내적·소프트맥스로 가중치 a 계산)과 Weight Sum 계층(가중합으로 맥락 벡터 c 계산)의 두 단계로 이루어진다
- 입력 전체를 고정 길이 벡터 하나에 압축하던 seq2seq의 한계를 매 시각 필요한 입력 정보를 새로 꺼내 쓰는 방식으로 해결한다

## 관련 개념
- [[Attention 계층]]
- [[Attention Weight 계층]]
- [[Weight Sum 계층]]
- [[seq2seq]]
- [[어텐션]]
- [[맥락 벡터]]
- [[가중치 a]]
- [[점수]]
- [[가중합]]
- [[Time 계층]]
- [[Encoder]]
- [[Decoder]]
- [[은닉 상태]]
- [[소프트맥스 함수]]
- [[얼라인먼트]]

## 출처
- 2026-11-17_attention.md#어텐션 > 5. Decoder 개선 ③: Attention 계층

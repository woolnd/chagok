# Attention Weight 계층

## 정의
Attention Weight 계층: Encoder가 출력한 각 단어의 벡터 hs와 Decoder LSTM의 은닉 상태 h를 내적해 유사도 점수 s를 구하고, 소프트맥스로 정규화해 가중치 a를 얻는다. 각 입력 단어를 얼마나 반영할지 정하는 단계다.

## 핵심 포인트
- 유사도 점수 s는 Decoder 은닉 상태 h와 hs의 내적으로 구한다 (s = h · hs)
- 점수 s를 소프트맥스로 정규화해 가중치 a를 얻는다 (a = softmax(s))
- Attention 계층은 Attention Weight 계층과 Weight Sum 계층의 두 단계로 계산된다
- Weight Sum 계층은 가중치 a로 hs를 가중합해 맥락 벡터 c를 만든다

## 관련 개념
- [[Attention 계층]]
- [[Weight Sum 계층]]
- [[Time Attention 계층]]
- [[어텐션]]
- [[점수]]
- [[가중치 a]]
- [[맥락 벡터]]
- [[가중합]]
- [[소프트맥스 함수]]
- [[얼라인먼트]]
- [[seq2seq]]
- [[Encoder]]
- [[Decoder]]
- [[은닉 상태]]

## 출처
- 2026-11-17_attention.md#어텐션 > 5. Decoder 개선 ③: Attention 계층

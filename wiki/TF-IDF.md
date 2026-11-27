# TF-IDF

## 정의
TF-IDF(Term Frequency-Inverse Document Frequency)는 여러 문서에 흔하게 나오는 단어의 가중치를 낮춰 BoW의 문제를 해결하는 방법이다. TF-IDF(t, d) = TF(t, d) × IDF(t), IDF(t) = log(N / df(t))로 계산한다.

## 핵심 포인트
- TF(t, d)는 문서 d에서 단어 t가 등장한 횟수, N은 전체 문서 수, df(t)는 단어 t가 등장한 문서 수다.
- 특정 문서에 자주 나오지만(TF가 큼) 다른 문서에는 잘 안 나오는(IDF가 큼) 단어일수록 큰 값을 받는다.
- 모든 문서에 나오는 단어는 IDF = log(N/N) = 0이 되어 문서를 구별하는 데 쓸모없는 단어로 처리된다.

## 관련 개념
- [[BoW]]
- [[동시발생 행렬]]
- [[희소 벡터]]
- [[통계 기반 기법]]
- [[CBOW]]

## 출처
- 2026-10-26_word_representation.md#자연어와 단어의 분산 표현 > 8. BoW와 TF-IDF

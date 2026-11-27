# GRU

## 정의
GRU(Gated Recurrent Unit)는 LSTM을 더 단순하게 만든 게이트가 추가된 RNN이다. LSTM은 매개변수가 많아 계산이 오래 걸리는데, GRU는 게이트를 이용한다는 아이디어는 그대로 두고 매개변수를 줄여 계산 시간을 줄인다.

## 핵심 포인트
- GRU에는 기억 셀이 없고, 시간 방향으로 전파되는 것은 은닉 상태 h뿐이다.
- 게이트는 LSTM의 3개(forget, input, output) 대신 reset 게이트 r과 update 게이트 z 2개만 쓴다.
- reset 게이트 r은 과거의 은닉 상태를 얼마나 무시할지 정하고, update 게이트 z는 은닉 상태를 얼마나 갱신할지 정한다.
- update 게이트 하나가 LSTM의 forget 게이트와 input 게이트 역할을 함께 한다.
- LSTM과 GRU 중 어느 쪽이 나은지는 문제와 하이퍼파라미터 설정에 따라 다르다.

## 관련 개념
- [[LSTM]]
- [[게이트]]
- [[기억 셀]]
- [[은닉 상태]]
- [[forget 게이트]]
- [[input 게이트]]
- [[output 게이트]]
- [[reset 게이트]]
- [[update 게이트]]
- [[RNN 언어 모델]]
- [[tanh]]
- [[아다마르 곱]]

## 출처
- 2026-11-09_gated_rnn.md#게이트가 추가된 RNN > 7. GRU

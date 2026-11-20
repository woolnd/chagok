# AlexNet

## 정의
AlexNet(2012)은 이미지 인식 대회 ILSVRC(ImageNet Large Scale Visual Recognition Challenge) 2012에서 기존 방법을 큰 차이로 이기며 딥러닝 붐을 일으켰다. 합성곱 5층 + 완전연결 3층 구조로 LeNet보다 크고 깊다.

## 핵심 포인트
- 활성화 함수로 ReLU를 사용하고, LRN(Local Response Normalization)으로 국소적 정규화를 하며, 드롭아웃(dropout)으로 과대적합(overfitting)을 억제한다.
- GPU(Graphics Processing Unit)를 활용해 대규모 학습을 가능하게 했다.
- 시그모이드는 층이 깊어지면 기울기 소실(vanishing gradient)이 생겨 ReLU로 바꾸었다.

## 관련 개념
- [[합성곱 신경망]]
- [[ReLU 함수]]
- [[기울기 소실]]
- [[드롭아웃]]
- [[과대적합]]
- [[LeNet]]
- [[VGG]]
- [[GoogLeNet]]
- [[ResNet]]
- [[LRN]]
- [[배치 정규화]]
- [[합성곱 계층]]
- [[완전연결]]
- [[시그모이드 함수]]

## 출처
- 2026-10-21_cnn.md#합성곱 신경망(CNN) > 5. 대표적인 CNN

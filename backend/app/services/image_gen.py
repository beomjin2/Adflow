"""이미지 생성 자리 — 지금은 랜덤 hue만 돌려주고, 프론트가 그라디언트로 렌더링한다
(frontend/src/theme.js의 bgGradient와 동일한 규칙). 나중에 실제 이미지 생성 API로 교체할 지점."""

import random


def random_hue() -> int:
    return random.randint(0, 359)

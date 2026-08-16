# -*- coding: utf-8 -*-
"""共用的動態基礎：彈簧物理與蘋果慣用的參數。

蘋果的 UI 動畫跟一般 easing curve 最根本的差別：
easing 是一條預先畫好的曲線，被打斷只能從頭再走；
彈簧有速度與慣性，被打斷時帶著當下的速度轉向新目標。

參數沿用 SwiftUI 的 response（週期）／damping（阻尼比）語意。
"""

import math


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def ease(t):
    """smoothstep。用在「由彈簧值再驅動的次要數值」上（環的掃描、進度條的填充），
    避免次要動畫跟著主彈簧一起過衝。"""
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class Spring:
    def __init__(self, value, response=0.42, damping=0.78):
        self.value = float(value)
        self.target = float(value)
        self.velocity = 0.0
        self.tune(response, damping)

    def tune(self, response, damping):
        self.omega = 2.0 * math.pi / max(0.05, response)
        self.zeta = damping

    def step(self, dt):
        dt = clamp(dt, 0.0, 1 / 30.0)   # 夾住 dt，掉幀時才不會炸開
        accel = self.omega * self.omega * (self.target - self.value) \
            - 2.0 * self.zeta * self.omega * self.velocity
        self.velocity += accel * dt
        self.value += self.velocity * dt

    def snap(self, value=None):
        if value is not None:
            self.target = float(value)
        self.value = self.target
        self.velocity = 0.0

    @property
    def settled(self):
        return abs(self.target - self.value) < 0.0008 and abs(self.velocity) < 0.0015


# 蘋果的不對稱慣例：進場彈一點（要抓注意力），退場平順（要讓開）。
PRESET = {
    "enter":   (0.52, 0.82),
    "exit":    (0.34, 1.00),
    "expand":  (0.40, 0.70),
    "collapse": (0.52, 1.00),
    "reveal":  (0.46, 0.72),
    "hide":    (0.36, 1.00),
    "content": (0.34, 1.00),
    "press":   (0.28, 0.55),
}

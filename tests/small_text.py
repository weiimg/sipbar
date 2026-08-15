# -*- coding: utf-8 -*-
"""小字專項比較：hinting、字級、字重、對比，各自對 14px 中文的影響。"""
import os
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor, QFont, QFontMetrics, QPainter, QPixmap,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv[:1])

TEXT = "最長連續（天）　累積補水（次）　完成一次補水 12/30"
BG = QColor(34, 35, 41)
INK3 = QColor(235, 235, 245, 168)     # 目前的第三層顏色（0.66）

CASES = [
    ("目前：14px Medium 全 hinting", dict(px=14, weight=QFont.Medium,
                                          hint=QFont.PreferFullHinting, color=INK3)),
    ("14px Medium 不 hinting", dict(px=14, weight=QFont.Medium,
                                    hint=QFont.PreferNoHinting, color=INK3)),
    ("14px Medium 垂直 hinting", dict(px=14, weight=QFont.Medium,
                                      hint=QFont.PreferVerticalHinting, color=INK3)),
    ("14px Bold", dict(px=14, weight=QFont.Bold, hint=QFont.PreferFullHinting, color=INK3)),
    ("15px Medium", dict(px=15, weight=QFont.Medium, hint=QFont.PreferFullHinting, color=INK3)),
    ("16px Medium", dict(px=16, weight=QFont.Medium, hint=QFont.PreferFullHinting, color=INK3)),
    ("14px Medium 提高對比 0.82", dict(px=14, weight=QFont.Medium,
                                        hint=QFont.PreferFullHinting,
                                        color=QColor(235, 235, 245, 209))),
    ("15px Medium 提高對比 0.82", dict(px=15, weight=QFont.Medium,
                                        hint=QFont.PreferFullHinting,
                                        color=QColor(235, 235, 245, 209))),
    ("家族名直接指定 Noto Sans TC Medium 15px",
     dict(px=15, family="Noto Sans TC Medium", weight=QFont.Normal,
          hint=QFont.PreferFullHinting, color=QColor(235, 235, 245, 209))),
]

ZOOM = 3
W, H = 400, 26
pad, label_h = 10, 24
sheet = QPixmap(W * ZOOM + pad * 2, (H * ZOOM + label_h) * len(CASES) + pad * 2)
sheet.fill(QColor("#3a3a3a"))
sp = QPainter(sheet)
sp.setFont(QFont("Noto Sans TC", 10))

y = pad
for label, cfg in CASES:
    pm = QPixmap(W, H)
    pm.fill(BG)
    p = QPainter(pm)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    f = QFont(cfg.get("family", "Noto Sans TC"))
    f.setPixelSize(cfg["px"])
    f.setWeight(cfg["weight"])
    f.setHintingPreference(cfg["hint"])
    f.setStyleStrategy(QFont.PreferAntialias)
    fm = QFontMetrics(f)
    p.setFont(f)
    p.setPen(cfg["color"])
    p.drawText(6, 4 + fm.ascent(), TEXT)
    p.end()

    big = pm.scaled(W * ZOOM, H * ZOOM, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    sp.drawPixmap(pad, y, big)
    sp.setPen(QColor("#f0f0f0"))
    sp.drawText(pad, y + H * ZOOM, W * ZOOM, label_h, Qt.AlignLeft | Qt.AlignVCenter, label)
    y += H * ZOOM + label_h

sp.end()
out = os.path.join(SCRATCH, "small_text.png")
sheet.save(out)
print("OK ->", out)

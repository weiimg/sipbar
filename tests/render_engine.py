# -*- coding: utf-8 -*-
"""用指定的字型引擎與字型渲染一段樣本。由 compare_engines.py 以子行程呼叫。

用法：render_engine.py <engine> <family> <out.png>
engine: default | freetype | gdi
"""
import os
import sys

engine, family, out = sys.argv[1], sys.argv[2], sys.argv[3]
if engine != "default":
    os.environ["QT_QPA_PLATFORM"] = f"windows:fontengine={engine}"

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv[:1])

SAMPLES = [
    ("連續 12 天", 28, QFont.Bold),
    ("今天已達標", 18, QFont.Bold),
    ("再 2 次維持連續　Streak 12", 16, QFont.Normal),
    ("最長連續（天）　累積補水（次）　估算水量（公升）", 14, QFont.Normal),
]

W, H = 560, 190
pm = QPixmap(W, H)
pm.fill(QColor(34, 35, 41))
p = QPainter(pm)
p.setRenderHint(QPainter.TextAntialiasing, True)

y = 8
for text, px, weight in SAMPLES:
    f = QFont(family)
    f.setPixelSize(px)
    f.setWeight(weight)
    f.setHintingPreference(QFont.PreferFullHinting)
    f.setStyleStrategy(QFont.PreferAntialias)
    fm = QFontMetrics(f)
    p.setFont(f)
    p.setPen(QColor(245, 245, 247) if weight == QFont.Bold else QColor(235, 235, 245, 214))
    y += fm.ascent()
    p.drawText(10, y, text)
    y += fm.descent() + 12
p.end()
pm.save(out)
print(f"{engine}|{family}|OK")

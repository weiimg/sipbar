# -*- coding: utf-8 -*-
"""字型改動前後對照：用實際的 UI 元件渲染，放大 2 倍比筆畫。"""
import os
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import stats_window as sw  # noqa: E402

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv[:1])

SAMPLES = [
    ("連續 12 天", "display"),
    ("今天已達標", "title"),
    ("再 2 次維持連續　·　護盾", "body"),
    ("最長連續（天）　累積補水（次）　估算水量（公升）", "caption"),
]

CONFIGS = [
    ("改前　Microsoft JhengHei UI（內文 Regular）", "Microsoft JhengHei UI",
     {"body": QFont.Normal, "caption": QFont.Normal}),
    ("改後　Noto Sans TC（內文 Medium）", "Noto Sans TC",
     {"body": QFont.Medium, "caption": QFont.Medium}),
]

W, H = 640, 220
ZOOM = 2
pad, label_h = 12, 26
sheet = QPixmap(W * ZOOM + pad * 2, (H * ZOOM + label_h + pad) * len(CONFIGS) + pad)
sheet.fill(QColor("#3a3a3a"))
sp = QPainter(sheet)
sp.setFont(QFont("Microsoft JhengHei UI", 10))

y0 = pad
for label, family, weights in CONFIGS:
    sw._FONTS.clear()
    sw.FONT = family
    for role, w in weights.items():
        px, _, tr = sw.TYPE[role]
        sw.TYPE[role] = (px, w, tr)

    pm = QPixmap(W, H)
    pm.fill(QColor(34, 35, 41))
    p = QPainter(pm)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    y = 10
    for text, role in SAMPLES:
        f = sw.font(role)
        fm = QFontMetrics(f)
        color = QColor(245, 245, 247) if role in ("display", "title") \
            else QColor(235, 235, 245, 214)
        p.setFont(f)
        p.setPen(color)
        y += fm.ascent()
        p.drawText(14, y, text)
        y += fm.descent() + 14
    p.end()

    big = pm.scaled(W * ZOOM, H * ZOOM, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    sp.drawPixmap(pad, y0, big)
    sp.setPen(QColor("#f0f0f0"))
    sp.drawText(pad, y0 + H * ZOOM, W * ZOOM, label_h, Qt.AlignLeft | Qt.AlignVCenter, label)
    y0 += H * ZOOM + label_h + pad

sp.end()
out = os.path.join(SCRATCH, "font_ab.png")
sheet.save(out)
print("OK ->", out)

# -*- coding: utf-8 -*-
"""把環單獨放大檢查各種值的排版。"""
import os
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import stats_window as sw  # noqa: E402

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
CASES = [(0, 7), (1, 7), (5, 7), (7, 7), (9, 7), (12, 7)]

ZOOM = 2
pad, label_h = 12, 24
size = 132
sheet = QPixmap((size * ZOOM + pad) * len(CASES) + pad, size * ZOOM + label_h + pad * 2)
sheet.fill(QColor("#22232A"))     # 卡片底色，才看得出實際對比
p = QPainter(sheet)
p.setFont(QFont("Microsoft JhengHei UI", 10))

for i, (v, t) in enumerate(CASES):
    ring = sw.Ring(v, t, size)
    ring.reveal = 1.0
    ring.show()
    app.processEvents()
    shot = ring.grab().scaled(size * ZOOM, size * ZOOM, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    x = pad + i * (size * ZOOM + pad)
    p.drawPixmap(x, pad, shot)
    p.setPen(QColor("#e8e8e8"))
    p.drawText(x, pad + size * ZOOM, size * ZOOM, label_h,
               Qt.AlignHCenter | Qt.AlignVCenter, f"{v} / {t}")
    ring.hide()

p.end()
out = os.path.join(SCRATCH, "ring_cases.png")
sheet.save(out)
print("OK ->", out)

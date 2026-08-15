# -*- coding: utf-8 -*-
"""把不同字型引擎 × 不同字型的渲染結果拼成一張對照圖，放大 2 倍看筆畫。"""
import os
import subprocess
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
RENDER = os.path.join(SCRATCH, "render_engine.py")

COMBOS = [
    ("default", "Microsoft JhengHei UI"),
    ("freetype", "Microsoft JhengHei UI"),
    ("gdi", "Microsoft JhengHei UI"),
    ("default", "Noto Sans TC"),
    ("freetype", "Noto Sans TC"),
    ("default", "Yu Gothic UI"),
]

paths = []
for i, (engine, family) in enumerate(COMBOS):
    out = os.path.join(SCRATCH, f"eng_{i}.png")
    r = subprocess.run([sys.executable, RENDER, engine, family, out],
                       capture_output=True, text=True)
    ok = os.path.exists(out)
    print(f"  {engine:<9} {family:<22} {'OK' if ok else 'FAILED: ' + r.stderr.strip()[:80]}")
    if ok:
        paths.append((f"{engine}　·　{family}", out))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv[:1])
ZOOM = 2
pad, label_h = 12, 26
first = QPixmap(paths[0][1])
tw, th = first.width() * ZOOM, first.height() * ZOOM
cols = 2
rows = (len(paths) + cols - 1) // cols
sheet = QPixmap(cols * (tw + pad) + pad, rows * (th + label_h + pad) + pad)
sheet.fill(QColor("#3a3a3a"))
p = QPainter(sheet)
p.setFont(QFont("Microsoft JhengHei UI", 10))
for i, (label, path) in enumerate(paths):
    pm = QPixmap(path).scaled(tw, th, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    x = pad + (i % cols) * (tw + pad)
    y = pad + (i // cols) * (th + label_h + pad)
    p.drawPixmap(x, y, pm)
    p.setPen(QColor("#f0f0f0"))
    p.drawText(x, y + th, tw, label_h, Qt.AlignLeft | Qt.AlignVCenter, label)
p.end()
out = os.path.join(SCRATCH, "engine_compare.png")
sheet.save(out)
print("OK ->", out)

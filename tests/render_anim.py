# -*- coding: utf-8 -*-
"""逐幀檢查紀錄視窗的進場動畫：卡片有沒有依序進來、數值有沒有跟著長。"""
import os
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"E:\Claude Project\Claude Inbox\喝水提醒桌寵")

import dashboard  # noqa: E402
import island as isl  # noqa: E402
import stats_window as sw  # noqa: E402

EVENTS = os.path.join(SCRATCH, "wp_dash", "events.jsonl")
if not os.path.exists(EVENTS):
    raise SystemExit("先跑 gen_dashboard.py 產資料")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

_real = dashboard.compute


def _boosted(cfg_, path):
    d = _real(cfg_, path)
    d["streak"]["streak"] = 12
    d["streak"]["saves_left"] = 1
    d["longest"] = max(d["longest"], 12)
    d["today"]["drinks"] = 5
    return d


dashboard.compute = _boosted

app = QApplication(sys.argv)
cfg = dict(isl.DEFAULT_CONFIG)
win = sw.StatsWindow(cfg, EVENTS)
win.show()
app.processEvents()
win.frame.stop()

# 決定性地重播動畫，不依賴 singleShot 的實際時序
win.sp_win.value = win.sp_win.velocity = 0.0
win.sp_win.target = 1.0
for c in win.cards:
    c.sp.value = c.sp.velocity = c.sp.target = 0.0

DT = 1 / 60.0
SHOTS_AT = [0.0, 0.10, 0.22, 0.36, 0.55, 0.90, 1.60]
shots, elapsed, started = [], 0.0, set()
next_shot = 0

for _ in range(int(2.2 / DT) + 1):
    for i, c in enumerate(win.cards):          # 重現錯開的起始時間
        if i not in started and elapsed * 1000 >= 40 + i * sw.STAGGER_MS:
            c.sp.target = 1.0
            started.add(i)
    if next_shot < len(SHOTS_AT) and elapsed >= SHOTS_AT[next_shot]:
        app.processEvents()
        shots.append((elapsed, win.grab()))
        next_shot += 1
    win.sp_win.step(DT)
    for c in win.cards:
        c.sp.step(DT)
        c.set_reveal(max(0.0, min(1.0, c.sp.value)))
    elapsed += DT

scale = 0.46
tw = int(win.width() * scale)
th = int(win.height() * scale)
pad, label_h = 10, 22
sheet = QPixmap((tw + pad) * len(shots) + pad, th + label_h + pad * 2)
sheet.fill(QColor("#4a4d55"))
p = QPainter(sheet)
p.setFont(QFont("Microsoft JhengHei UI", 9))
for i, (t, pm) in enumerate(shots):
    small = pm.scaled(tw, th, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    x = pad + i * (tw + pad)
    p.drawPixmap(x, pad, small)
    p.setPen(QColor("#e8e8e8"))
    p.drawText(x, pad + th, tw, label_h, Qt.AlignHCenter | Qt.AlignVCenter, f"{t * 1000:.0f}ms")
p.end()
out = os.path.join(SCRATCH, "stats_anim.png")
sheet.save(out)
print("卡片數:", len(win.cards), " 取樣:", [f"{t*1000:.0f}ms" for t, _ in shots])
print("OK ->", out)

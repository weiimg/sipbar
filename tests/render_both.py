# -*- coding: utf-8 -*-
"""同時渲染「剛開始（稀疏）」與「用了一陣子（豐富）」兩種狀態。

之前只用豐富的假資料設計，稀疏狀態從沒被檢視過——而使用者看到的正是稀疏狀態。
"""
import json
import os
import shutil
import sys
from datetime import datetime, timedelta

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import dashboard  # noqa: E402
import island as isl  # noqa: E402
import stats_window as sw  # noqa: E402

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
cfg = dict(isl.DEFAULT_CONFIG)
T = cfg["daily_target_drinks"]

# ---- 稀疏：今天一天，剛好達標（重現使用者截圖的狀態）
SPARSE_DIR = os.path.join(SCRATCH, "wp_sparse")
shutil.rmtree(SPARSE_DIR, ignore_errors=True)
os.makedirs(SPARSE_DIR, exist_ok=True)
SPARSE = os.path.join(SPARSE_DIR, "events.jsonl")
today = datetime.now()
# 換日在早上 5 點，不能直接用 now 的日期當鍵——凌晨跑會差一天
key = dashboard._day_key(today, cfg["day_rollover_hour"])
with open(SPARSE, "w", encoding="utf-8") as f:
    f.write(json.dumps({"ts": today.replace(hour=9).isoformat(timespec="seconds"),
                        "day": key, "event": "day_start"}, ensure_ascii=False) + "\n")
    for i in range(T):
        ts = today.replace(hour=10 + i, minute=5).isoformat(timespec="seconds")
        f.write(json.dumps({"ts": ts, "day": key, "event": "remind", "drinks": i},
                           ensure_ascii=False) + "\n")
        f.write(json.dumps({"ts": ts, "day": key, "event": "drink", "from_state": "THIRSTY",
                            "responded": True, "wait_active_s": 120, "drinks": i + 1},
                           ensure_ascii=False) + "\n")

RICH = os.path.join(SCRATCH, "wp_dash", "events.jsonl")

panels = []
for label, path, boost in (("剛開始：今天第一天達標", SPARSE, False),
                           ("用了一陣子：連續 12 天", RICH, True)):
    _real = dashboard.compute
    if boost:
        def _b(c, p, _r=_real):
            d = _r(c, p)
            d["streak"]["streak"] = 12
            d["streak"]["saves_left"] = 1
            d["longest"] = max(d["longest"], 12)
            d["today"]["drinks"] = 5
            return d
        dashboard.compute = _b
    win = sw.StatsWindow(cfg, path)
    win.show()
    win.frame.stop()
    win.refresh(animate=False)
    app.processEvents()
    # 不捲動之後改成拍每一頁。稀疏狀態只有一頁（沒有紀錄時不分頁），
    # 豐富狀態三頁——**兩者的頁數不同本身就是要看的東西**。
    shots = []
    for i in range(win.stack.count()):
        win.seg.set_index(i, animate=False)
        win.stack.setCurrentIndex(i)
        win.cards = win.page_cards[i]
        for c in win.cards:
            c.sp.snap(1.0)
            c.set_reveal(1.0)
        win.sp_win.snap(1.0)
        win.setWindowOpacity(1.0)
        app.processEvents()
        shots.append(win.grab())
    panels.append((label, shots))
    dashboard.compute = _real

pad, label_h = 14, 26
rows = []
for label, shots in panels:
    rows.append((label, sum(s.width() + pad for s in shots) - pad,
                 max(s.height() for s in shots), shots))
tw = max(r[1] for r in rows) + pad * 2
th = sum(r[2] + label_h + pad for r in rows) + pad
sheet = QPixmap(tw, th)
sheet.fill(QColor("#4a4d55"))
p = QPainter(sheet)
p.setFont(QFont("Microsoft JhengHei UI", 10))
y = pad
for label, _w, h, shots in rows:
    x = pad
    for s in shots:
        p.drawPixmap(x, y, s)
        x += s.width() + pad
    p.setPen(QColor("#f0f0f0"))
    p.drawText(pad, y + h + 2, tw, label_h, Qt.AlignLeft | Qt.AlignVCenter,
               f"{label}（{len(shots)} 頁）")
    y += h + label_h + pad
p.end()
out = os.path.join(SCRATCH, "stats_both.png")
sheet.save(out)
print("OK ->", out)

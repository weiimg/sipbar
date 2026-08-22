# -*- coding: utf-8 -*-
"""成就那一頁的列間距三種對照。挑完把選中的值寫回 build_achievements_card。"""
import os
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import stats_window as sw  # noqa: E402
import island as isl  # noqa: E402
import dashboard  # noqa: E402

from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

EVENTS = os.path.join(SCRATCH, "wp_dash", "events.jsonl")
if not os.path.exists(EVENTS):
    raise SystemExit("先跑 gen_dashboard.py 產資料")

app = QApplication(sys.argv)
cfg = dict(isl.DEFAULT_CONFIG)
_real = dashboard.compute


def _boosted(cfg_, path):
    d = _real(cfg_, path)
    d["streak"]["streak"] = 12
    d["streak"]["saves_left"] = 1
    d["today"]["drinks"] = 5
    return d


dashboard.compute = _boosted

win = sw.StatsWindow(cfg, EVENTS)
win.show()
win.frame.stop()
win.refresh(animate=False)
app.processEvents()

PAGE = 2                                    # 成就
win.seg.set_index(PAGE, animate=False)
win.stack.setCurrentIndex(PAGE)
win.cards = win.page_cards[PAGE]
card = win.page_cards[PAGE][0]

shots = []
for gap, note in ((8, "修改前"), (16, "修改後")):
    card.box.setSpacing(gap)
    for c in win.cards:
        c.sp.snap(1.0)
        c.set_reveal(1.0)
    win.sp_win.snap(1.0)
    win.setWindowOpacity(1.0)
    card.layout().activate()
    app.processEvents()
    # 這裡不呼叫 _fit_height()：它會 adjustSize()，兩張圖的視窗寬度就不一樣，
    # 對照圖看起來像改了寬度。高度夠不夠由 render_stats_window.py 驗。
    need = win.stack.widget(PAGE).sizeHint().height()
    shots.append((f"{note}　列距 {gap}px　成就頁需要 {need}px", win.grab()))

pad = 16
sheet = QPixmap(pad + sum(s.width() + pad for _l, s in shots),
                max(s.height() for _l, s in shots) + pad * 2 + 26)
sheet.fill(QColor("#4a4d55"))
p = QPainter(sheet)
p.setFont(QFont("Microsoft JhengHei UI", 10))
x = pad
for label, shot in shots:
    p.drawPixmap(x, pad, shot)
    p.setPen(QColor("#e8e8e8"))
    p.drawText(x + 8, pad + max(s.height() for _l, s in shots) + 18, label)
    x += shot.width() + pad
p.end()
out = os.path.join(SCRATCH, "achievements_gap.png")
sheet.save(out)
print("內容可用", win.stack.height(), "px ->", out)

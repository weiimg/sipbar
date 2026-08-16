# -*- coding: utf-8 -*-
"""把紀錄視窗完整畫出來（含捲動區全長），確認排版。"""
import os
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import stats_window as sw  # noqa: E402
import island as isl  # noqa: E402

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

EVENTS = os.path.join(SCRATCH, "wp_dash", "events.jsonl")   # gen_dashboard.py 產的擬真資料
if not os.path.exists(EVENTS):
    raise SystemExit("先跑 gen_dashboard.py 產資料")

app = QApplication(sys.argv)
cfg = dict(isl.DEFAULT_CONFIG)

# 假資料的連續是 0，看不到火焰點亮的樣子。這裡蓋掉幾個值來看「有在連續」的狀態。
import dashboard  # noqa: E402
_real = dashboard.compute


def _boosted(cfg_, path):
    d = _real(cfg_, path)
    d["streak"]["streak"] = 12
    d["streak"]["saves_left"] = 1
    d["longest"] = max(d["longest"], 12)
    d["today"]["drinks"] = 5
    return d


dashboard.compute = _boosted

win = sw.StatsWindow(cfg, EVENTS)
win.show()
win.frame.stop()
win.refresh(animate=False)          # 直接看定格，不等動畫
app.processEvents()

# 每一頁各拍一張。不捲動之後「完整內容」就等於「每一頁」，沒有看不到的部分。
shots = []
for i, (label, _b) in enumerate(sw.PAGES):
    win.seg.set_index(i, animate=False)
    win.stack.setCurrentIndex(i)
    win.cards = win.page_cards[i]
    for c in win.cards:
        c.sp.snap(1.0)
        c.set_reveal(1.0)
    win.sp_win.snap(1.0)
    win.setWindowOpacity(1.0)
    app.processEvents()
    shots.append((label, win.grab()))

pad = 16
sheet = QPixmap(pad + sum(s.width() + pad for _l, s in shots),
                max(s.height() for _l, s in shots) + pad * 2 + 26)
sheet.fill(QColor("#4a4d55"))
p = QPainter(sheet)
p.setFont(QFont("Microsoft JhengHei UI", 9))
x = pad
for label, shot in shots:
    p.drawPixmap(x, pad, shot)
    p.setPen(QColor("#e8e8e8"))
    p.drawText(x, pad + shot.height() + 18, label)
    x += shot.width() + pad
p.end()

out = os.path.join(SCRATCH, "stats_window.png")
sheet.save(out)

# 高度驗證。這一項要留著：日後往任何一頁加東西，會先在這裡被擋下來，
# 而不是等使用者看到被切掉的字。不捲動的面板沒有「往下拉就看得到」這條退路。
avail = win.stack.height()
print(f"視窗 {win.width()}x{win.height()}　內容可用 {avail}px")
fails = []
for i, (label, _b) in enumerate(sw.PAGES):
    need = win.stack.widget(i).sizeHint().height()
    fits = need <= avail
    print(f"  {'ok  ' if fits else 'FAIL'} {label}：需要 {need}px")
    if not fits:
        fails.append(label)
print("OK ->", out)
sys.exit(1 if fails else 0)

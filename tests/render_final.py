# -*- coding: utf-8 -*-
"""正式版各狀態外觀對照，確認排版。"""
import os
import shutil
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import island as isl  # noqa: E402

TEST_DIR = os.path.join(SCRATCH, "wp_render")
shutil.rmtree(TEST_DIR, ignore_errors=True)
isl.DATA_DIR = TEST_DIR
isl.STATE_PATH = os.path.join(TEST_DIR, "state.json")
isl.EVENTS_PATH = os.path.join(TEST_DIR, "events.jsonl")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
w = isl.Island(dict(isl.DEFAULT_CONFIG))
w.tick_timer.stop()
w.peek_timer.stop()
w.frame.stop()
w.hold_timer.stop()
w.show()

rows = [
    ("收合（隱藏前後／探頭）", isl.NORMAL, 0.00, 0),
    ("口渴 · 展開", isl.THIRSTY, 1.00, 0),
    ("口渴 · 停留 0.35", isl.THIRSTY, 0.35, 1),
    ("虛弱 · 停留 0.50", isl.WEAK, 0.50, 2),
    ("倒地 · 全展開", isl.COLLAPSED, 1.00, 2),
    ("喝了", isl.SATISFIED, 1.00, 3),
    ("達標", isl.SATISFIED, 1.00, 6),
    ("啟動打招呼", isl.NORMAL, 1.00, 0),
]

pad, label_h, row_h = 10, 24, isl.PILL_MAX[1] + 30
sheet = QPixmap(isl.WIN_W + pad * 2, (row_h + label_h + pad) * len(rows) + pad)
sheet.fill(QColor("#4a4d55"))   # 中灰底才看得出投影
p = QPainter(sheet)
p.setFont(QFont("Microsoft JhengHei", 9))

y = pad
for label, state, t, drinks in rows:
    w.state = state
    w.drinks = drinks
    if label == "啟動打招呼":
        w.message, w.sub_message = "我在這裡", "滑鼠移到螢幕上緣中間就能叫我"
    elif label == "喝了":
        w._refresh_message("喝了，還剩 3 次")
    elif label == "達標":
        w._refresh_message("今天達標了，收工")
    else:
        w._refresh_message()
    w.sp_expand.value = w.sp_expand.target = t
    w.sp_expand.velocity = 0.0
    # 這支直接設 w.state，繞過了 _enter，水位彈簧不會自己跟上——要手動同步，
    # 否則畫出來的是上一個狀態的水位，比對出來的結論是假的。
    w.sp_level.value = w.sp_level.target = isl.pixelface.LEVEL[state]
    w.sp_level.velocity = 0.0
    w.sp_reveal.value = w.sp_reveal.target = 1.0
    w.sp_content.value = w.sp_content.target = 1.0 if t > 0.62 else 0.0
    w.update()
    shot = w.grab().copy(0, 0, isl.WIN_W, row_h)
    p.drawPixmap(pad, y, shot)
    p.setPen(QColor("#e5e5e5"))
    p.drawText(pad, y + row_h, isl.WIN_W, label_h, Qt.AlignLeft | Qt.AlignVCenter, label)
    y += row_h + label_h + pad

p.end()
out = os.path.join(SCRATCH, "island_final.png")
sheet.save(out)
print("OK ->", out)

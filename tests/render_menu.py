# -*- coding: utf-8 -*-
"""系統匣選單定格，並驗證沒有任何一行會溢出。

溢出這件事一定要有機器在守。狀態字串是動態組出來的（連續天數破百、
暫停到某個時刻、目標次數兩位數…），人工挑的例子永遠會漏掉最長的那個組合——
第一版就是副標重複了標題的內容，長到跑出容器外才被眼睛抓到。
"""
import os
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import menu as traymenu  # noqa: E402
import theme  # noqa: E402

from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

# 最長情況：三位數的量、兩位數的目標、以及最長的那組選單文字
CASES = [
    ("一般", ("今天 1 / 10 次", "約 150 cc　·　下次約 42 分後"),
     [("記錄補水", None), ("暫停提醒 2 小時", None), ("喝水紀錄", None),
      ("設定", None), (None, None), ("結束程式", None, True)]),
    ("暫停中", ("今天 7 / 12 次", "已暫停，23:45 恢復"),
     [("記錄補水", None), ("恢復提醒", None), ("喝水紀錄", None),
      ("設定", None), (None, None), ("結束程式", None, True)]),
    ("達標", ("今天 12 / 12 次", "約 2400 cc　·　今日已達標"),
     [("記錄補水", None), ("暫停提醒 2 小時", None), ("喝水紀錄", None),
      ("設定", None), (None, None), ("結束程式", None, True)]),
]

fails = []
shots = []

for th in ("dark", "light"):
    theme.apply(th)
    for label, head, items in CASES:
        m = traymenu.TrayMenu(head, items)
        m.show()
        app.processEvents()

        # 可用寬度就是內容區：兩側各扣一個 PAD_H
        avail = traymenu.WIDTH - traymenu.PAD_H * 2
        checks = [("標題", head[0], m._f_head), ("副標", head[1], m._f_sub)]
        checks += [("項目 " + it[0], it[0], m._f_item)
                   for it in m.items if it[0]]
        for what, text, f in checks:
            need = QFontMetrics(f).horizontalAdvance(text)
            if need > avail:
                print(f"  FAIL {th}/{label} {what}：需要 {need}px / 可用 {avail}px"
                      f"　「{text}」")
                fails.append(f"{th}/{label}/{what}")

        if th == "dark" or label == "一般":
            shots.append(m.grab())
        if label == "一般":
            m.hover = m._rows[0][2]
            m.update()
            app.processEvents()
            shots.append(m.grab())

print(f"寬度檢查：{len(CASES) * 2} 種情況，"
      f"{'全部放得下' if not fails else f'{len(fails)} 項溢出'}")

pad = 16
sheet = QPixmap(pad + sum(s.width() + pad for s in shots),
                max(s.height() for s in shots) + pad * 2)
sheet.fill(QColor("#8A8D95"))
p = QPainter(sheet)
x = pad
for s in shots:
    p.drawPixmap(x, pad, s)
    x += s.width() + pad
p.end()

out = os.path.join(SCRATCH, "tray_menu.png")
sheet.save(out)
theme.apply("dark")
print("OK ->", out)
sys.exit(1 if fails else 0)

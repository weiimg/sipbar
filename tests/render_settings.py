# -*- coding: utf-8 -*-
"""把設定頁畫出來，並驗證內容放得下。

設定頁跟紀錄三頁一樣不捲動，所以同樣需要一個會在「內容超出高度」時擋下來的檢查——
沒有捲軸就沒有「往下拉就看得到」這條退路。
"""
import os
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"E:\Claude Project\Claude Inbox\喝水提醒桌寵")

import settings as appsettings  # noqa: E402
import stats_window as sw  # noqa: E402

from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

EVENTS = os.path.join(SCRATCH, "wp_dash", "events.jsonl")
if not os.path.exists(EVENTS):
    raise SystemExit("先跑 gen_dashboard.py 產資料")

app = QApplication(sys.argv)

shots = []
fails = []

# 兩種情況都要看：有填體重（推導出來的次數）與沒填（用預設值）。
# 沒填是新使用者的第一眼，那一版比較容易被忘記檢查。
for label, weight in (("有填體重", 65), ("沒填體重", None), ("清除紀錄的確認狀態", 65)):
    cfg = dict(appsettings.DEFAULTS)
    cfg["weight_kg"] = weight
    cfg["daily_target_drinks"] = appsettings.effective_target(cfg)

    win = sw.StatsWindow(cfg, EVENTS)
    win.show()
    win.frame.stop()
    win._switch_mode("settings", animate=False)
    if "確認" in label:
        # 破壞性動作的第二段。這個狀態一樣要看得到——它是使用者真的會停在
        # 上面做決定的那一格，卻最容易只在程式碼裡存在、從沒被人看過。
        win.settings_page.danger._arm()
    for c in win.cards:
        c.sp.snap(1.0)
        c.set_reveal(1.0)
    win.sp_win.snap(1.0)
    win.setWindowOpacity(1.0)
    app.processEvents()

    avail = win.root.height()
    need = win.settings_page.sizeHint().height()
    fits = need <= avail
    print(f"  {'ok  ' if fits else 'FAIL'} {label}：需要 {need}px / 可用 {avail}px"
          f"　視窗 {win.width()}x{win.height()}")
    if not fits:
        fails.append(label)
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

out = os.path.join(SCRATCH, "settings_page.png")
sheet.save(out)
print("OK ->", out)
sys.exit(1 if fails else 0)

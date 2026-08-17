# -*- coding: utf-8 -*-
"""把設定頁畫出來，並驗證內容放得下。

設定頁跟紀錄三頁一樣不捲動，所以同樣需要一個會在「內容超出高度」時擋下來的檢查——
沒有捲軸就沒有「往下拉就看得到」這條退路。
"""
import os
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

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
        #
        # 就地確認已經拿掉了（理由見 DangerRow 的 docstring：確認鍵會長在
        # 觸發鍵剛剛的位置，手快點兩下就誤刪），現在走 ConfirmOverlay。
        # 這支腳本一度還在呼叫已經不存在的 danger._arm()，跑起來直接 
        # AttributeError——沒有人跑它，所以壞了很久沒被發現。
        win._ask_reset()
    for c in win.cards:
        c.sp.snap(1.0)
        c.set_reveal(1.0)
    win.sp_win.snap(1.0)
    win.setWindowOpacity(1.0)
    app.processEvents()

    # 設定頁可捲動，所以不驗「塞得下」。要守的是兩件跟捲動無關的事：
    # 視窗高度必須跟紀錄頁一致（換頁不能跳動），以及沒有卡片被壓扁。
    bar = win.pane.area.verticalScrollBar()
    squashed = [c.height() for c in win.settings_page.cards if c.height() < 80]
    # 跟紀錄頁比，不要寫死數字：視窗高度由紀錄那三頁決定，
    # 那邊的卡片內容一改（例如環換成杯子）高度就會變，寫死的斷言只會變成假失敗。
    win._switch_mode("stats", animate=False)
    app.processEvents()
    stats_h = win.height()
    win._switch_mode("settings", animate=False)
    app.processEvents()
    ok = win.height() == stats_h and not squashed
    print(f"  {'ok  ' if ok else 'FAIL'} {label}："
          f"視窗 {win.width()}x{win.height()}　內容 {win.settings_page.height()}px"
          f"　可視 {win.root.height()}px　捲動範圍 0..{bar.maximum()}")
    if squashed:
        print(f"       有卡片被壓扁：{squashed}")
    if not ok:
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

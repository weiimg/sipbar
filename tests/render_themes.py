# -*- coding: utf-8 -*-
"""深色與淺色主題並排定格，用眼睛比對。

顏色沒有辦法用斷言驗——「這個灰在白底上看不看得見」只有看得出來。
所以這支不回傳成敗，它的用途是每次改調色盤都產一張圖來看。

唯一會擋下來的是對比檢查：小字的對比度低於門檻就報，
那條是有客觀標準的（WCAG 的 4.5:1 是給正文的，這裡的次要文字放寬到 3.5:1）。
"""
import os
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import dashboard  # noqa: E402
import settings as appsettings  # noqa: E402
import stats_window as sw  # noqa: E402

from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

EVENTS = os.path.join(SCRATCH, "wp_dash", "events.jsonl")
if not os.path.exists(EVENTS):
    raise SystemExit("先跑 gen_dashboard.py 產資料")

app = QApplication(sys.argv)

# 假資料的連續是 0，看不到火焰點亮的樣子
_real = dashboard.compute


def _boosted(cfg_, path):
    d = _real(cfg_, path)
    d["streak"]["streak"] = 12
    d["streak"]["saves_left"] = 1
    d["longest"] = max(d["longest"], 12)
    d["today"]["drinks"] = 5
    return d


dashboard.compute = _boosted


def luminance(c):
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())


def contrast(fg, bg):
    """fg 帶透明度時，先跟 bg 疊合再算——半透明的字，實際對比是疊合後的顏色。"""
    a = fg.alpha() / 255.0
    mixed = QColor(int(fg.red() * a + bg.red() * (1 - a)),
                   int(fg.green() * a + bg.green() * (1 - a)),
                   int(fg.blue() * a + bg.blue() * (1 - a)))
    l1, l2 = luminance(mixed), luminance(bg)
    lo, hi = sorted((l1, l2))
    return (hi + 0.05) / (lo + 0.05)


MIN_RATIO = 3.5
fails = []
shots = []

for name in ("dark", "light"):
    pal = sw.apply_theme(name)
    sw._FONTS.clear()          # 字體本身沒變，但顏色是寫在 stylesheet 裡的

    print(f"\n{name}")
    card = pal.card_top
    for role, css in (("主要文字", pal.ink), ("次要文字", pal.ink2), ("第三層", pal.ink3)):
        # 從 css 反解出 rgba
        nums = css[css.index("(") + 1:css.index(")")].split(",")
        col = QColor(int(nums[0]), int(nums[1]), int(nums[2]), int(float(nums[3]) * 255))
        ratio = contrast(col, card)
        ok = ratio >= MIN_RATIO
        print(f"  {'ok  ' if ok else 'FAIL'} {role} 在卡片上的對比 {ratio:.2f}:1")
        if not ok:
            fails.append(f"{name}/{role}")

    cfg = dict(appsettings.DEFAULTS)
    cfg["weight_kg"] = 65
    cfg["daily_target_drinks"] = appsettings.effective_target(cfg)

    win = sw.StatsWindow(cfg, EVENTS)
    win.show()
    win.frame.stop()
    win.refresh(animate=False)
    app.processEvents()
    for c in win.cards:
        c.sp.snap(1.0)
        c.set_reveal(1.0)
    win.sp_win.snap(1.0)
    win.setWindowOpacity(1.0)
    app.processEvents()
    shots.append(win.grab())

    win._switch_mode("settings", animate=False)
    for c in win.cards:
        c.sp.snap(1.0)
        c.set_reveal(1.0)
    app.processEvents()
    shots.append(win.grab())

pad = 16
sheet = QPixmap(pad + sum(s.width() + pad for s in shots),
                max(s.height() for s in shots) + pad * 2 + 26)
sheet.fill(QColor("#8A8D95"))
p = QPainter(sheet)
p.setFont(QFont("Microsoft JhengHei UI", 9))
x = pad
for label, shot in zip(("深色 · 紀錄", "深色 · 設定", "淺色 · 紀錄", "淺色 · 設定"), shots):
    p.drawPixmap(x, pad, shot)
    p.setPen(QColor("#101114"))
    p.drawText(x, pad + shot.height() + 18, label)
    x += shot.width() + pad
p.end()

out = os.path.join(SCRATCH, "theme_compare.png")
sheet.save(out)
sw.apply_theme("dark")      # 還原，免得影響後面跑的腳本
print("\nOK ->", out)
sys.exit(1 if fails else 0)

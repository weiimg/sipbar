# -*- coding: utf-8 -*-
"""合成字體的字樣：換掉的 101 個字形，跟換之前並排。

`test_font_build.py` 量得出寬度對不對，量不出**字形本身有沒有轉壞**——
qu2cu 轉曲線時如果誤差給太大，字會微微變形；那只有眼睛看得出來。
所以這支把每一個被換掉的字都畫出來，一個都不漏。

放大兩倍是**把字級乘二重畫**，不是把畫好的圖放大。第一版是後者，
結果 64px 的字上出現缺角與貫穿的斜線，看起來像字形轉壞了——那是把帶 hinting 的
點陣圖用最近鄰放大兩倍的產物，字體本身完全正常（改成原生 160px 重畫就乾淨了）。

**驗字形的工具自己不能製造假象。** 差點就照著這個假象去改建置腳本。
"""
import os
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
sys.path.insert(0, os.path.join(APP, "tools"))

from PySide6.QtGui import (  # noqa: E402
    QColor, QFont, QFontDatabase, QFontMetrics, QPainter, QPixmap,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

import build_font  # noqa: E402
import stats_window as sw  # noqa: E402
import typeface  # noqa: E402

app = QApplication(sys.argv)
typeface.ensure_loaded()
sw.apply_theme("dark")

# 換之前的樣子。來源字體不在 assets/ 裡，是 tools/fontsrc/ 的建置輸入。
before_id = QFontDatabase.addApplicationFont(
    os.path.join(build_font.SRC, build_font.WEIGHTS[0][1]))
BEFORE = QFontDatabase.applicationFontFamilies(before_id)[0]

ZOOM = 2
COL_W = 520
PAD = 16
SPECIMENS = [
    ("display", "0123456789"),
    ("title", "0.9.0-beta"),
    ("headline", "今天 3/7 次"),
    ("body", "23:00 起改為每 109 分"),
    ("body", "1400cc / 65 公斤 / 75 分鐘"),
    ("caption", r"C:\Users\PC\AppData\Local\WaterPet"),
    # 被換掉的字全部列出來。少看一個就是少驗一個。
    ("caption", "".join(chr(c) for c in build_font.SUBSTITUTE[:47])),
    ("caption", "".join(chr(c) for c in build_font.SUBSTITUTE[47:])),
]


def strip(family):
    fonts = []
    for role, text in SPECIMENS:
        px, weight, tracking = sw.TYPE[role]
        f = QFont()
        f.setFamilies([family])
        f.setPixelSize(px * ZOOM)          # 放大字級，不是放大點陣圖
        f.setWeight(weight)
        f.setHintingPreference(QFont.PreferFullHinting)
        if tracking:
            f.setLetterSpacing(QFont.AbsoluteSpacing, tracking * ZOOM)
        fonts.append((f, text, QFontMetrics(f)))

    h = PAD + sum(fm.height() + PAD for _f, _t, fm in fonts)
    pm = QPixmap(COL_W * ZOOM, h)
    pm.fill(sw.PAL.card_top)
    p = QPainter(pm)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    y = PAD
    for f, text, fm in fonts:
        p.setFont(f)
        p.setPen(sw.PAL.ink_a(245))
        p.drawText(PAD, y + fm.ascent(), text)
        y += fm.height() + PAD
    p.end()
    return pm


cols = [("換之前：Noto Sans TC", strip(BEFORE)),
        (f"換之後：{typeface.FAMILY}", strip(typeface.FAMILY))]
gap, top = 20, 46
h = max(s.height() for _l, s in cols)
sheet = QPixmap((COL_W * ZOOM + gap) * 2 + gap, h + top + gap)
sheet.fill(QColor("#3d4048"))
p = QPainter(sheet)
for i, (label, s) in enumerate(cols):
    x = gap + i * (COL_W * ZOOM + gap)
    p.setFont(QFont("Microsoft JhengHei UI", 11, QFont.Bold))
    p.setPen(QColor("#e8e8e8"))
    p.drawText(x, 30, label)
    p.drawPixmap(x, top, s)
p.end()

out = os.path.join(SCRATCH, "font_specimen.png")
sheet.save(out)
print(f"畫了 {len(build_font.SUBSTITUTE)} 個換掉的字形，兩欄並排")
print("OK ->", out)

# -*- coding: utf-8 -*-
"""產生 README 功能區塊的四個圖示。

## 為什麼自己畫，不用現成圖示集

這個專案沒有一張外來的圖，杯子、臉、火焰、環全部是程式畫出來的。
插一組 Material 或 emoji 進來，風格會立刻斷掉。

## 為什麼是像素風

跟 `docs/demo.webp` 的桌布、`docs/stats-window.png` 的示意圖同一套。
前一版是平滑的向量圖示（漸層、抗鋸齒的圓角），跟同一頁上的像素杯放在一起
就是兩種畫風貼在一起——`onboard.IslandPreview._build_wallpaper` 的註解
早就講過這件事，只是當時只套用在桌布上。

## 為什麼不直接截程式畫面

前兩個概念（島藏在螢幕上緣、點一下就記錄）在 `onboard.IslandPreview` 裡演過，
但那張圖是 464x150 的橫幅，縮到四欄的寬度只剩 58px 高，藥丸連形狀都看不出來。
圖示要的是輪廓不是實景。

火焰不再重用 `stats_window.Flame._path()`——那是一條貝茲曲線，點陣化之後
邊緣是灰階漸變，跟旁邊三個硬邊的圖示對不起來。改成字串圖形手排，
形狀跟紀錄視窗裡那把火是同一個意思，但畫法跟著這裡的畫風走。

## 畫法

在 32×32 的格子上畫，再用最近鄰放大 8 倍到 256。直接畫 256 的話每個「像素」
都是真的一像素，那就只是一張普通的圖——**像素感來自放大倍率，不是解析度。**

不規則的形狀（火焰、游標、勾）用字串圖形，跟 `pixelface.FACES` 同一套寫法；
規則的形狀（外框、藥丸、圓環）用算的——手排一個圓比寫程式畫還容易出錯。

## 顏色

取 `theme.DARK` 的語意色。那組是校準在深色底上的，但它們同時也夠深，
放在 GitHub 的淺色主題上一樣讀得到；反過來拿 LIGHT 那組（壓深過的）
放到深色底上就會糊掉。README 兩種主題都要能看。

用法：python tools/make_feature_icons.py
"""
import os
import sys

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import theme  # noqa: E402

OUT = os.path.join(ROOT, "docs")

G = 32                       # 格子邊長。四個圖示共用，才會是同一個像素尺度
SCALE = 8                    # 輸出 256，README 顯示約 80
P = theme.DARK

ACCENT = QColor(P.accent)
GREEN = QColor(P.green)
FLAME = QColor(P.flame)
FLAME2 = QColor(P.flame2)
# 結構線用中灰。純黑在深色主題上消失，純白在淺色主題上消失，中灰兩邊都活。
LINE = QColor("#8A8B95")

FLAME_ART = (
    "......##........",
    ".....####.......",
    "....#####.......",
    "....######......",
    "...#######......",
    "...########.....",
    "..#########.....",
    "..##########....",
    ".###########....",
    ".############...",
    ".############...",
    ".############...",
    "..###########...",
    "..##########....",
    "...########.....",
    "....######......",
)
FLAME_CORE_ART = (
    "...##...",
    "..####..",
    ".######.",
    ".######.",
    ".######.",
    "..####..",
)
# 游標自己帶描邊。白色游標在 GitHub 的淺色主題上會整個消失——
# 底是 #FAFAFA，游標是 #FFFFFF，差 5 階。README 兩種主題都要能看。
# `#` 是白色實心，`o` 是深色描邊。
CURSOR_ART = (
    "oo.........",
    "o#o........",
    "o##o.......",
    "o###o......",
    "o####o.....",
    "o#####o....",
    "o######o...",
    "o#######o..",
    "o########o.",
    "o#####oooo.",
    "o##o##o....",
    "oo.o##o....",
    "...o##o....",
    "....o#o....",
    ".....oo....",
)
CHECK_ART = (
    "........##",
    ".......###",
    "......###.",
    "#....###..",
    "##..###...",
    "###.###...",
    ".#####....",
    "..###.....",
    "...#......",
)


def px(p, x, y, w, h, color):
    p.fillRect(QRect(int(x), int(y), int(w), int(h)), color)


def sprite(p, art, x, y, color, outline=None):
    """`#` 用 color 畫，`o` 用 outline 畫。其餘留空。"""
    for r, line in enumerate(art):
        for c, ch in enumerate(line):
            if ch == "#":
                px(p, x + c, y + r, 1, 1, color)
            elif ch == "o" and outline is not None:
                px(p, x + c, y + r, 1, 1, outline)


def frame(p, x, y, w, h, color, t=2):
    """空心矩形。"""
    px(p, x, y, w, t, color)
    px(p, x, y + h - t, w, t, color)
    px(p, x, y, t, h, color)
    px(p, x + w - t, y, t, h, color)


def pill(p, x, y, w, h, color):
    """兩端收成階梯的橫向膠囊。角各切一格就夠——在 32 格上切兩格會變成六角形。"""
    px(p, x + 1, y, w - 2, h, color)
    px(p, x, y + 1, w, h - 2, color)


def ring(p, cx, cy, r, color, t=2):
    """圓環。用算的不用手排——手排一個圓比寫程式畫還容易出錯。"""
    for yy in range(int(cy - r) - 1, int(cy + r) + 2):
        for xx in range(int(cx - r) - 1, int(cx + r) + 2):
            d = ((xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2) ** 0.5
            if r - t <= d <= r:
                px(p, xx, yy, 1, 1, color)


def hidden():
    """平常完全隱藏：一台螢幕，島只從上緣露出一截。"""
    def draw(p):
        frame(p, 2, 7, 28, 20, LINE)
        px(p, 4, 9, 24, 16, QColor(0, 0, 0, 0))      # 挖空，只留外框
        pill(p, 11, 5, 10, 5, ACCENT)                # 島騎在上緣，一半在外
    return draw


def one_tap():
    """按一下就記錄：藥丸、游標、打勾。"""
    def draw(p):
        pill(p, 2, 12, 19, 9, ACCENT)
        sprite(p, CHECK_ART, 21, 3, GREEN)
        sprite(p, CURSOR_ART, 12, 15, QColor("#FFFFFF"), outline=QColor("#2A2B31"))
    return draw


def streak():
    """連續天數會累積：火焰。"""
    def draw(p):
        sprite(p, FLAME_ART, 8, 8, FLAME)
        sprite(p, FLAME_CORE_ART, 12, 18, FLAME2)
    return draw


def rhythm():
    """依作息自動調整：時鐘。"""
    def draw(p):
        ring(p, 16, 16, 13, LINE, t=2)
        px(p, 15, 8, 2, 9, ACCENT)                   # 分針，指上
        px(p, 15, 15, 8, 2, ACCENT)                  # 時針，指右
        px(p, 14, 14, 4, 4, ACCENT)                  # 軸心
    return draw


ICONS = [("feat-hidden.png", hidden), ("feat-tap.png", one_tap),
         ("feat-streak.png", streak), ("feat-rhythm.png", rhythm)]


def render(draw):
    img = QImage(G, G, QImage.Format_RGBA8888)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, False)
    draw(p)
    p.end()
    return img.scaled(G * SCALE, G * SCALE, Qt.IgnoreAspectRatio,
                      Qt.FastTransformation)


def main():
    app = QApplication.instance() or QApplication(sys.argv)   # noqa: F841
    os.makedirs(OUT, exist_ok=True)
    for name, fn in ICONS:
        path = os.path.join(OUT, name)
        if not render(fn()).save(path):
            print(f"FAIL 寫不出 {path}")
            return 1
        print(f"  {name:<18} {os.path.getsize(path) / 1024:>5.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

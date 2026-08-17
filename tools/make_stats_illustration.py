# -*- coding: utf-8 -*-
"""產生使用說明裡的紀錄視窗示意圖 —— docs/stats-window.png。

## 為什麼不用截圖

原本那張是三個視窗的真實截圖。在 GitHub 上大概 800px 寬，一個視窗只剩 260px，
裡面每一行字都在 4px 高——**那些文字沒有人讀得到，它們只是雜訊**。
而且每次改一個標籤（例如護盾那列多一行「已消耗」）截圖就過期，沒有人會發現。

## 為什麼可以畫，不怕說謊

`make_demo.py` 立過一條規矩：重畫一套「看起來很像」的島，只要正式版改了樣子，
宣傳圖就會開始說謊。那條規矩針對的是**看起來像截圖的假圖**。

像素風不一樣——它一眼就宣告自己是插畫，不會有人拿它當「介面實際長這樣」。
它要傳達的只有結構：三個分頁、今天有進度、紀錄有熱圖、成就有清單。
那些是不會變的東西。

畫風跟 `docs/demo.webp` 的桌布同一套（`onboard.IslandPreview._build_wallpaper`
的理由：螢幕裡站的是一隻像素杯子，配上平滑的東西就變成兩種畫風貼在一起）。

## 一個字都不放

分頁叫什麼由 `USAGE.md` 的圖說負責（「三個分頁：今天、紀錄、成就」）。
圖上再寫一次是重複，而且中文字縮到這個尺寸就是糊掉的一團。
順序由左到右對應圖說，讀得出來。

杯子是真的——`pixelface.draw_cup()`，跟島上那顆同一份程式。

## 形狀用字串圖形寫

跟 `pixelface.FACES` 同一套寫法。用座標算火焰跟勾勾，改一次就要重算一次；
寫成字串是**看著就知道長什麼樣**，而這張圖唯一的工作就是形狀。

用法：python tools/make_stats_illustration.py
"""
import os
import sys

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pixelface  # noqa: E402
import theme  # noqa: E402

OUT = os.path.join(ROOT, "docs", "stats-window.png")

# 先畫小的再放大，跟桌布同一個做法：放大用最近鄰，像素邊緣才不會被抹糊。
# 直接畫大的話每個「像素」都是真的一像素，那就只是一張普通的向量圖。
SCALE = 4
W, H = 640, 176

MARGIN, GAP = 9, 13
WIN_W = (W - MARGIN * 2 - GAP * 2) // 3
WIN_H = H - MARGIN * 2

# 視窗的圓角。像素風的圓角是階梯狀的，每一列往內縮幾格寫死在這裡。
CORNER = (3, 1, 1)

# 火焰要有尖端才讀得出是火。第一版是上下對稱的六列，出來是一顆橘色的球。
FLAME = (
    "..#...",
    "..##..",
    ".###..",
    ".####.",
    "######",
    "######",
    ".####.",
)
FLAME_CORE = (
    "..#..",
    ".###.",
    ".###.",
)
# 圓環：八角形，四個角各切一格。畫成方形在這個尺寸下看起來就是方形。
RING = (
    ".####.",
    "#....#",
    "#....#",
    "#....#",
    "#....#",
    ".####.",
)
CHECK = (
    ".....#",
    "....##",
    "#..##.",
    "####..",
    ".##...",
)


def px(p, x, y, w, h, color):
    p.fillRect(QRect(int(x), int(y), int(w), int(h)), color)


def sprite(p, art, x, y, color, cell=1):
    """把字串圖形畫出來。`#` 是實心，其餘留空。"""
    for r, line in enumerate(art):
        for c, ch in enumerate(line):
            if ch == "#":
                px(p, x + c * cell, y + r * cell, cell, cell, color)


def bar(p, x, y, w, pal, alpha=40, h=3):
    """一段代表文字的色塊。畫字會糊，畫塊反而讀得出「這裡有一行字」。"""
    px(p, x, y, w, h, pal.veil(alpha))


def rounded(p, x, y, w, h, color):
    """階梯圓角的矩形。CORNER 是由外往內每一列要縮掉幾格。"""
    inset = list(CORNER)
    px(p, x, y + len(inset), w, h - len(inset) * 2, color)
    for i, n in enumerate(inset):
        px(p, x + n, y + i, w - n * 2, 1, color)
        px(p, x + n, y + h - 1 - i, w - n * 2, 1, color)


def window(p, x, y, pal, active_tab):
    """視窗外殼：外框、標題區、分頁列。三個分頁共用。"""
    rounded(p, x, y, WIN_W, WIN_H, pal.bg_bottom)
    px(p, x + CORNER[0], y, WIN_W - CORNER[0] * 2, 1, pal.veil(24))   # 頂緣高光

    bar(p, x + 9, y + 9, 34, pal, 78, h=5)                            # 標題
    bar(p, x + 9, y + 18, 22, pal, 34)                                # 副標

    seg_y, seg_h = y + 27, 10                                         # 分頁列
    seg_w = (WIN_W - 18) // 3
    px(p, x + 9, seg_y, seg_w * 3, seg_h, pal.veil(10))
    px(p, x + 9 + seg_w * active_tab, seg_y, seg_w, seg_h, pal.veil(28))
    for i in range(3):
        bar(p, x + 9 + seg_w * i + seg_w // 2 - 7, seg_y + 4, 14, pal,
            80 if i == active_tab else 30)
    return seg_y + seg_h + 6


def card(p, x, y, w, h, pal):
    rounded(p, x, y, w, h, pal.card_top)
    px(p, x + CORNER[0], y, w - CORNER[0] * 2, 1, pal.veil(18))
    return y + h + 6


def panel_today(p, x, y, pal):
    """今天：火焰、連續天數、像素杯，下面一排本週的圓環。"""
    cx, cw = x + 9, WIN_W - 18
    top = card(p, cx, y, cw, 56, pal)

    sprite(p, FLAME, cx + 9, y + 15, pal.flame, cell=3)
    sprite(p, FLAME_CORE, cx + 11, y + 27, pal.flame2, cell=3)

    bar(p, cx + 34, y + 16, 22, pal, 96, h=12)                # 大數字
    bar(p, cx + 34, y + 33, 26, pal, 34)                      # 「連續達標」

    pixelface.draw_cup(p, cx + cw - 18, y + 24, 0.7, pixelface.THIRSTY,
                       pixelface.GLASS, pixelface.WATER, pixelface.INK,
                       cell=2, face=True)
    bar(p, cx + cw - 29, y + 42, 22, pal, 34)                 # 「5 / 7 次」

    card(p, cx, top, cw, 44, pal)                             # 本週也是一張卡
    bar(p, cx + 8, top + 8, 20, pal, 60, h=4)
    for i in range(7):
        # 一格綠色＝那天達標，其餘藍色＝有進度但沒滿。跟真的一樣。
        sprite(p, RING, cx + 9 + i * 14, top + 19,
               pal.green if i == 2 else pal.accent, cell=2)


def panel_trail(p, x, y, pal):
    """紀錄：熱圖 ＋ 統計數字。熱圖本來就是格子，最適合像素風。"""
    cx, cw = x + 9, WIN_W - 18
    top = card(p, cx, y, cw, 70, pal)

    bar(p, cx + 7, y + 7, 20, pal, 60, h=4)
    # 12 週 × 7 天，左疏右密——那是一個「越用越常用」的人的樣子。
    # 手排不用亂數：亂數每次建置都不一樣，而且多半看起來像雜訊。
    ROWS = (
        "...12233233",
        "..122333233",
        ".1223.33323",
        "..23233332.",
        ".12.3233233",
        "...2233.323",
        "..122332332",
    )
    gx, gy = cx + 9, y + 14
    TONE = {".": None, "1": 110, "2": 190, "3": 255}
    for r, line in enumerate(ROWS):
        for c, ch in enumerate(line):
            a = TONE[ch]
            if a is None:
                col = pal.veil(9)
            elif ch == "3":
                col = pal.green
            else:
                col = QColor(pal.accent.red(), pal.accent.green(),
                             pal.accent.blue(), a)
            px(p, gx + c * 5, gy + r * 5, 4, 4, col)

    for i in range(3):                                        # 三個統計數字
        sx = cx + 9 + i * ((cw - 18) // 3)
        bar(p, sx, y + 53, 13, pal, 92, h=7)
        bar(p, sx, y + 63, 20, pal, 30)

    card(p, cx, top, cw, 30, pal)                             # 回應率那張小卡
    for i in range(2):
        sx = cx + 14 + i * ((cw - 28) // 2)
        bar(p, sx, top + 8, 13, pal, 92, h=7)
        bar(p, sx, top + 18, 22, pal, 30)


def panel_badges(p, x, y, pal):
    """成就：一列一個勾，最後一列還沒完成。"""
    cx, cw = x + 9, WIN_W - 18
    card(p, cx, y, cw, 106, pal)
    bar(p, cx + 7, y + 7, 20, pal, 60, h=4)

    for i in range(6):
        ry = y + 16 + i * 15
        done = i < 5
        px(p, cx + 7, ry + 1, 10, 10, pal.accent if done else pal.veil(14))
        if done:
            sprite(p, CHECK, cx + 9, ry + 4, pal.card_top)
        bar(p, cx + 22, ry + 1, 28, pal, 84, h=4)
        bar(p, cx + 22, ry + 8, 40, pal, 26)
        px(p, cx + cw - 28, ry + 4, 20, 3, pal.veil(12))      # 進度條
        px(p, cx + cw - 28, ry + 4, 20 if done else 8, 3,
           pal.accent if done else pal.veil(40))


def main():
    app = QApplication.instance() or QApplication(sys.argv)   # noqa: F841
    theme.apply("dark")
    pal = theme.active()

    img = QImage(W, H, QImage.Format_RGBA8888)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, False)             # 像素不要被磨圓

    for i, panel in enumerate((panel_today, panel_trail, panel_badges)):
        x = MARGIN + i * (WIN_W + GAP)
        panel(p, x, window(p, x, MARGIN, pal, i), pal)
    p.end()

    big = img.scaled(W * SCALE, H * SCALE, Qt.IgnoreAspectRatio,
                     Qt.FastTransformation)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    big.save(OUT)
    print(f"{OUT}")
    print(f"  {big.width()}x{big.height()}（{W}x{H} 放大 {SCALE} 倍）  "
          f"{os.path.getsize(OUT) / 1024:.0f}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

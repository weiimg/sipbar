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

# 像素版的 Bliss，縮到 24×16。色票取自 onboard.IslandPreview._build_wallpaper()
# 那張桌布——demo.webp 與社群動畫用的是同一組，這裡只是把它縮小手排。
# 不直接呼叫那個函式：它的雲寫死在格子座標上（是為 464px 寬排的），
# 畫布一縮，三團雲會全部擠成一團。
WALL_COLORS = {
    "a": "#265ABE", "b": "#3A76D6", "c": "#5E9CE8",   # 天空由深到淺
    "d": "#8CC2F2", "e": "#BEE0F8",
    "w": "#FFFFFF",                                    # 雲
    "1": "#8CC63F", "2": "#6BA82E", "3": "#4E8C22",   # 山丘：頂緣亮、越深越暗
}
WALL_ART = (
    "aaaaaaaaaaaaaaaaaaaaaaaa",
    "aaaaaaaaaaaaaaaaaaaaaaaa",
    "bbbbbwwwbbbbbbbbbbbbbbbb",
    "bbbbwwwwwbbbbbbbbbbbbbbb",
    "cccccccccccccccccccwwccc",
    "ccccccccccccccccccwwwwcc",
    "dddddddddddddddddddddddd",
    "dddddddddddddddddddddddd",
    "eeeeeeeeeeeeeeeeeeeeeeee",
    "1111eeeeeeeeeeeeeeeeeeee",
    "2221111eeeeeeeeeeeeeeeee",
    "3332221111eeeeeeeeeeeeee",
    "3333322211111eeeeeeeeeee",
    "3333333222211111111eeeee",
    "3333333333222222211111ee",
    "333333333333333322222211",
)

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
# 游標。形狀照 Windows 那支箭頭：直的左緣、斜的右緣、到最寬處切一刀（缺口），
# 然後左邊留一隻小腳、尾巴往右下延伸。
#
# 兩版之前是憑感覺排的，尾巴接不起來；上一版是把大游標砍短，比例又跑掉——
# **箭頭的比例在「缺口」那一刀，不在總長度**，等比例縮才對。
#
# 描邊不寫在這裡：交給 sprite() 自己長，手排描邊漏一格就是缺一個口。
CURSOR_ART = (
    "#........",
    "##.......",
    "###......",
    "####.....",
    "#####....",
    "######...",
    "#######..",
    "########.",
    "#####....",
    "##.###...",
    "#..###...",
    "....###..",
    ".....##..",
)


def px(p, x, y, w, h, color):
    p.fillRect(QRect(int(x), int(y), int(w), int(h)), color)


def sprite(p, art, x, y, color, outline=None):
    """把字串圖形畫出來。`#` 是實心，其餘留空。

    給了 outline 就自己往外長一圈描邊。**不要手排描邊**——漏一格就是缺一個口，
    而那種缺口在 32 格上看不出來，放大 8 倍才會現形。規則的東西用算的。
    """
    cells = {(c, r) for r, line in enumerate(art)
             for c, ch in enumerate(line) if ch == "#"}
    if outline is not None:
        edge = {(c + dx, r + dy) for c, r in cells
                for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - cells
        for c, r in edge:
            px(p, x + c, y + r, 1, 1, outline)
    for c, r in cells:
        px(p, x + c, y + r, 1, 1, color)


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
    """平常完全隱藏：一台筆電、Bliss 桌布，島從螢幕上緣冒出來。

    前一版是空心的螢幕外框加一個藍色藥丸——看得懂但沒有場景，
    而這一格要講的正是「它出現在你的桌面上」。畫成筆電＋桌布之後，
    島是黑的（跟真的一樣），在藍天上一眼就找得到。
    """
    def draw(p):
        px(p, 3, 4, 26, 18, QColor("#3A3D45"))       # 上蓋
        px(p, 3, 4, 26, 1, QColor("#4E525C"))        # 頂緣亮邊
        for r, line in enumerate(WALL_ART):          # 螢幕裡的桌布
            for c, ch in enumerate(line):
                px(p, 4 + c, 5 + r, 1, 1, QColor(WALL_COLORS[ch]))
        px(p, 3, 22, 26, 1, QColor("#2C2F35"))       # 轉軸
        px(p, 1, 23, 30, 2, QColor("#43464E"))       # 底座
        px(p, 13, 24, 6, 1, QColor("#2C2F35"))       # 開闔的凹槽

        # 島。黑色藥丸，跟正式版同一個顏色。
        #
        # 刻意往下挪一格，讓上面露出一線天空。**貼齊上緣的話讀起來是瀏海**
        # ——像硬體缺口，不像「時間到才滑下來的東西」。正式版確實是貼齊的，
        # 但這是示意圖，要傳達的是「它出現了」。
        pill(p, 12, 6, 8, 4, QColor("#16171B"))
    return draw


def one_tap():
    """按一下就記錄：藥丸上的進度點多亮一格。

    用產品自己的語言講「記錄了」——島上就是這排點，按一下多一格。
    比打勾誠實：打勾是通用符號，進度點是這個工具真的會發生的事。

    游標放在綠色那格的正下方，**不能蓋到它**。前一版的游標壓在點上，
    而那一格正是這張圖唯一要講的東西。
    """
    def draw(p):
        pill(p, 2, 6, 28, 14, ACCENT)
        # 四格不是七格。README 上只有 80px，七格的話每格剩兩像素，
        # 綠色那格看不出來——而那格是這張圖唯一要講的東西。
        for i in range(4):
            if i == 2:
                col = GREEN                          # 剛剛多的那一格
            elif i < 2:
                col = QColor("#FFFFFF")              # 已經喝過的
            else:
                col = QColor(255, 255, 255, 90)      # 還沒的
            px(p, 5 + i * 6, 10, 5, 5, col)
        sprite(p, CURSOR_ART, 17, 16, QColor("#FFFFFF"), outline=QColor("#2A2B31"))
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

# -*- coding: utf-8 -*-
"""產生 icon.ico —— 工作列、Alt+Tab、開機捷徑用的應用程式圖示。

## 為什麼有底板

前一版是**透明背景上的一個杯子**，那是 2010 年代的做法，而且有實害：
杯壁是淺灰的，在淺色桌面上 32px 以下整個消失，只剩中間那塊藍色的水——
變成一個藍色方塊，認不出是什麼。

底板給的是「任何背景上都一樣的輪廓」。底色直接用這個 app 的識別藍，
杯子改成白的壓在上面，對比拉到最高，16px 還讀得出「杯子 + 水面」。

系統匣不受影響：那顆圖示是 island._tray_icon() 每次即時畫的（會跟著狀態變臉），
跟這個檔案產出的 icon.ico 是兩回事。

## 為什麼每個尺寸各畫一次

**每個尺寸都各自原生繪製，不是把大圖縮小。**
像素圖一旦被重新取樣就毀了（邊緣糊掉、格線對不上），而 16/32/48… 之間的比例
不是整數倍，縮放一定會產生半個格子。所以逐一畫。

**每個尺寸都有臉，包括 16px。** 舊版在格距 1–2px 時把臉拿掉，理由是
「糊成一團反而破壞杯子的輪廓」——那個理由在舊配色下成立（淺水配深臉，
小尺寸本來就分不開），但換成深水配白臉之後臉是讀得出來的。
而這個工具的識別不是一個杯子，是**一隻有表情的杯子**：小圖示拿掉臉，
它就變成一般的飲水提醒了。

用法：python make_icon.py
"""
import os
import sys

from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor, QImage, QLinearGradient, QPainter, QPainterPath,
)
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixelface as pf  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(HERE, "icon.ico")

SIZES = [16, 32, 48, 64, 128, 256]

# 圖示不用「水滿」（level 1.0）。滿杯整片都是水，杯子的形狀就消失了，
# 16px 下就只是一個方塊、毫無識別度。留一段空的杯口，
# 「玻璃杯 + 水面」這個組合才讀得出來——圖示要的是輪廓，不是狀態。
ICON_LEVEL = 0.75

# 格距是查表不是算比例。**格距一定是整數**（像素圖不能有半格），而杯子是
# 11×12 格，所以「杯子佔畫布幾成」只能落在少數幾個值上：256 挑得到 61%，
# 32 只有 38% 或 75% 兩種，中間沒有東西。
# 用 size×比例 再取整的寫法，會在 16px 算出比底板還大的杯子（實測過）。
CELL = {256: 13, 128: 7, 64: 3, 48: 3, 32: 2, 16: 1}

# 圓角半徑也要跟著尺寸收。固定比例在 16px 上會把四個角各啃掉 3–4px，
# 而那個尺寸的杯子已經佔到 75%，被啃掉的就是杯壁本身。
RADIUS = {256: 0.22, 128: 0.22, 64: 0.22, 48: 0.20, 32: 0.16, 16: 0.12}

PLATE_TOP = QColor("#5CB3F0")
PLATE_BOTTOM = QColor("#2C7FC4")
CUP_GLASS = QColor("#FFFFFF")       # 杯壁：純白，對比拉到最高
CUP_WATER = QColor("#1F6FB0")       # 水：深藍
CUP_INK = QColor("#FFFFFF")         # 臉：白的，浮在深藍的水上

# ## 為什麼水是深的、臉是白的
#
# 第一版是反過來的（淺水 + 深臉），那在大尺寸好看，但 16px 直接壞掉：
# 杯壁是純白、水是接近白的淺藍，**小尺寸下沒有任何一格能把兩者分開**，
# 整個下半部糊成一塊淺色方塊，杯子的輪廓消失，剩下「藍底上一個淺色方塊」。
# 在 Raycast 的搜尋結果裡看到的就是那個。
#
# 換成深水之後，三個值各自分開：白杯壁 / 深藍水體 / 中藍底板，
# 連水面線都還看得見——而水面線正是「這是一杯水」唯一的線索。
#
# 臉跟著翻成白色。**臉要留在每一個尺寸**，包括 16px：這個工具的識別不是
# 一個杯子，是一隻有表情的杯子，小圖示把臉拿掉就變成一般的飲水提醒。
# 深水配白臉在 16px 實測讀得出來，比原本「淺水配深臉」還清楚。


def render(size):
    cell = CELL[size]
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)

    path = QPainterPath()
    r = size * RADIUS[size]
    path.addRoundedRect(QRectF(0, 0, size, size), r, r)
    g = QLinearGradient(0, 0, 0, size)
    g.setColorAt(0.0, PLATE_TOP)
    g.setColorAt(1.0, PLATE_BOTTOM)
    p.setPen(Qt.NoPen)
    p.fillPath(path, g)

    pf.draw_cup(
        p, size / 2.0, size / 2.0, ICON_LEVEL, pf.NORMAL,
        CUP_GLASS, CUP_WATER, CUP_INK,
        cell=cell,
        face=True,
    )
    p.end()

    img = img.convertToFormat(QImage.Format_RGBA8888)
    return Image.frombytes("RGBA", (size, size), img.constBits().tobytes())


def main():
    app = QApplication.instance() or QApplication(sys.argv)   # noqa: F841
    frames = [render(s) for s in SIZES]
    # append_images 讓每個尺寸用自己那張原生圖，而不是讓 Pillow 去縮放
    frames[-1].save(ICON_PATH, format="ICO",
                    sizes=[(s, s) for s in SIZES],
                    append_images=frames[:-1])

    with Image.open(ICON_PATH) as ico:
        got = sorted(ico.ico.sizes())
    print(f"{ICON_PATH}  {os.path.getsize(ICON_PATH) / 1024:.1f}KB")
    print(f"  內含尺寸：{got}")
    missing = set((s, s) for s in SIZES) - set(got)
    if missing:
        print(f"  FAIL 缺少尺寸：{sorted(missing)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

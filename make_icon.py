# -*- coding: utf-8 -*-
"""產生 icon.ico —— 工作列、Alt+Tab、開機捷徑用的應用程式圖示。

**每個尺寸都各自原生繪製，不是把大圖縮小。**
像素圖一旦被重新取樣就毀了（邊緣糊掉、格線對不上），而 16/32/48… 之間的比例
不是整數倍，縮放一定會產生半個格子。所以逐一畫。

小尺寸（格距 1–2px）不畫臉：臉只有 7–14px，糊成一團反而破壞杯子的輪廓。
小圖示要的是「一眼認出這是什麼」。

用法：python make_icon.py
"""
import os
import sys

from PIL import Image
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixelface as pf  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(HERE, "icon.ico")

# 這些尺寸配 cell = S // 14 剛好都落在整數格距上，且留得出邊界：
#   16→1(11x12)  32→2(22x24)  48→3(33x36)  64→4(44x48)  128→9  256→18
# 24 會落在 cell=1、圖只佔一半，所以不放。
SIZES = [16, 32, 48, 64, 128, 256]

# 圖示不用「水滿」（level 1.0）。滿杯整片都是水，杯子的形狀就消失了，
# 16px 下就只是一個藍色方塊、毫無識別度。留一段空的杯口，
# 「玻璃杯 + 水面」這個組合才讀得出來——圖示要的是輪廓，不是狀態。
ICON_LEVEL = 0.75


def render(size):
    cell = max(1, size // 14)
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    pf.draw_cup(
        p, size / 2.0, size / 2.0, ICON_LEVEL, pf.NORMAL,
        pf.GLASS, pf.WATER, pf.INK,
        cell=cell,
        face=cell >= 3,
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

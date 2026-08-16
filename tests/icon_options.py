# -*- coding: utf-8 -*-
"""app icon 的三個方向，並排比較。挑定之後把選中的畫法搬進 make_icon.py。

現行圖示看起來舊，原因很具體：它是透明背景上的一個圖形。那是 2010 年代的
做法，現在桌面圖示都有圓角底板——底板給的是「任何背景上都一樣的輪廓」，
而透明圖形在淺色桌面上會直接消失（杯壁是淺灰的）。

系統匣不受影響：那顆圖示是 island._tray_icon() 每次即時畫的，會跟著狀態變臉，
跟 icon.ico 是兩回事。
"""
import os
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPixmap,
)
from PySide6.QtWidgets import QApplication

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, APP)

import pixelface as pf  # noqa: E402

SIZES = [256, 64, 32, 16]
ICON_LEVEL = 0.75


def plate(p, size, top, bottom, radius_ratio=0.22):
    """圓角底板。半徑用比例不是固定值——固定值在 16px 上會變成幾乎直角。"""
    r = size * radius_ratio
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), r, r)
    g = QLinearGradient(0, 0, 0, size)
    g.setColorAt(0.0, QColor(top))
    g.setColorAt(1.0, QColor(bottom))
    p.setPen(Qt.NoPen)
    p.fillPath(path, g)


# 每個尺寸的格距是查表不是算比例。格距一定是整數（像素圖不能有半格），
# 而 cup_size = 11×12 格，所以「杯子佔畫布幾成」只能落在少數幾個值上：
# 256 可以挑到 61%，32 只有 38% 或 75% 兩種，中間沒有東西。
# 用比例去乘再取整，就會像第一版那樣在 16px 算出比底板還大的杯子。
CELL = {256: 13, 128: 7, 64: 3, 48: 3, 32: 2, 16: 1}
# 小尺寸的圓角要跟著收。固定比例在 16px 上會把四個角各啃掉 3–4px，
# 而那時候杯子已經佔到 75%，啃到的就是杯壁。
RADIUS = {256: 0.22, 128: 0.22, 64: 0.22, 48: 0.20, 32: 0.16, 16: 0.12}


def cup(p, size, cell, glass, water, ink, face):
    pf.draw_cup(p, size / 2.0, size / 2.0, ICON_LEVEL, pf.NORMAL,
                glass, water, ink, cell=cell, face=face)


def render_a(size):
    """A 深色底板 + 原本的杯子。改動最小，只補上底板。"""
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    plate(p, size, "#3A3F4B", "#23262E", RADIUS[size])
    cell = CELL[size]
    cup(p, size, cell, pf.GLASS, pf.WATER, pf.INK, face=cell >= 3)
    p.end()
    return img


def render_b(size):
    """B 藍色底板 + 白杯。藍色是這個 app 的識別色，底板直接用它最好認。"""
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    plate(p, size, "#5CB3F0", "#2C7FC4", RADIUS[size])
    cell = CELL[size]
    cup(p, size, cell, QColor("#FFFFFF"), QColor("#DCEEFC"),
        QColor("#2C7FC4"), face=cell >= 3)
    p.end()
    return img


def render_c(size):
    """C 不加底板，把杯子本身重畫得更厚實。保留「透明圖形」的純粹。

    杯壁加粗到兩格、杯子放大：現行版本杯壁只有一格，16px 下細到幾乎看不見。
    """
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    cell = CELL[size]
    cup(p, size, cell, QColor("#E8ECF4"), pf.WATER, QColor("#FFFFFF"),
        face=cell >= 3)
    p.end()
    return img


VARIANTS = [("A 深色底板", render_a), ("B 藍色底板", render_b),
            ("C 無底板·加厚", render_c)]
# 兩種桌面底色都要看：現行圖示在淺色底上會消失，那正是要解掉的問題之一
BACKDROPS = [("深色桌面", "#1E2026"), ("淺色桌面", "#E9EBEF")]


def main():
    app = QApplication.instance() or QApplication(sys.argv)   # noqa: F841
    import typeface
    typeface.ensure_loaded()          # 不載的話標籤全是豆腐方塊
    import stats_window as sw
    sw.apply_theme("dark")

    # 每一格都放大到同一個顯示尺寸，比較的才是「這個尺寸下畫得出多少細節」，
    # 而不是「哪張圖比較大」。16px 放大 8 倍看起來很粗，那正是它真實的樣子。
    BOX, GAP, LABEL = 128, 18, 26
    row_h = BOX + LABEL + GAP
    grid_w = len(SIZES) * (BOX + GAP) + GAP
    sheet = QPixmap(grid_w + 140, len(BACKDROPS) * (len(VARIANTS) * row_h + 46) + 30)
    sheet.fill(QColor("#7C8089"))
    p = QPainter(sheet)
    p.setFont(sw.font("caption"))

    y = 30
    for bname, bcolor in BACKDROPS:
        p.setPen(QColor("#FFFFFF"))
        p.drawText(20, y + 14, bname)
        y += 24
        block_h = len(VARIANTS) * row_h
        p.fillRect(130, y, grid_w, block_h, QColor(bcolor))
        ink = QColor("#FFFFFF") if bname.startswith("深") else QColor("#22242A")
        for vi, (vname, fn) in enumerate(VARIANTS):
            ry = y + vi * row_h
            p.setPen(QColor("#FFFFFF"))
            p.drawText(20, ry + BOX // 2, vname)
            for si, s in enumerate(SIZES):
                x = 130 + GAP + si * (BOX + GAP)
                im = fn(s)
                p.drawPixmap(x, ry + LABEL,
                             QPixmap.fromImage(im).scaled(BOX, BOX))
                p.setPen(ink)
                p.drawText(x, ry + 16, f"{s}px")
        y += block_h + 22
    p.end()
    out = os.path.join(HERE, "icon_options.png")
    sheet.save(out)
    print("OK ->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

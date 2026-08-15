# -*- coding: utf-8 -*-
"""驗證「半透明視窗會失去次像素渲染」這個說法到底成不成立。

判準：次像素（ClearType）渲染會在字緣produce 彩色條紋，也就是同一個像素的 R/G/B 不相等。
灰階抗鋸齒則 R=G=B。直接數有色像素的比例就知道用的是哪一種。
"""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

app = QApplication(sys.argv)

TEXT = "喝水紀錄 連續 12 天 Streak 12"
BG = QColor(34, 35, 41)


def make_font(px=16, hint=QFont.PreferFullHinting, strategy=QFont.PreferAntialias, weight=QFont.Normal):
    f = QFont("Microsoft JhengHei UI")
    f.setPixelSize(px)
    f.setWeight(weight)
    f.setHintingPreference(hint)
    f.setStyleStrategy(strategy)
    return f


def colored_ratio(img):
    """回傳「R/G/B 不相等」的像素佔非背景像素的比例。"""
    if img.format() != QImage.Format_ARGB32:
        img = img.convertToFormat(QImage.Format_ARGB32)
    colored = ink = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() < 8:
                continue
            if abs(c.red() - BG.red()) + abs(c.green() - BG.green()) + abs(c.blue() - BG.blue()) < 12:
                continue
            ink += 1
            if max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue()) > 14:
                colored += 1
    return (colored / ink * 100) if ink else 0.0, ink


def draw(dev, f):
    p = QPainter(dev)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    if isinstance(dev, QPixmap) or isinstance(dev, QImage):
        p.fillRect(0, 0, dev.width(), dev.height(), BG)
    p.setFont(f)
    p.setPen(QColor(245, 245, 247))
    p.drawText(6, 24, TEXT)
    p.end()


class W(QWidget):
    def __init__(self, translucent, f):
        super().__init__()
        self.f = f
        if translucent:
            self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(360, 36)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.fillRect(self.rect(), BG)
        p.setFont(self.f)
        p.setPen(QColor(245, 245, 247))
        p.drawText(6, 24, TEXT)


f = make_font()
print("繪製目標對彩色條紋（次像素渲染）的影響：")

pm = QPixmap(360, 36)
draw(pm, f)
r, n = colored_ratio(pm.toImage())
print(f"  不透明 QPixmap        彩色像素 {r:5.1f}%  （墨跡 {n}）")

img = QImage(360, 36, QImage.Format_ARGB32_Premultiplied)
img.fill(Qt.transparent)
draw(img, f)
r, n = colored_ratio(img)
print(f"  半透明 QImage         彩色像素 {r:5.1f}%  （墨跡 {n}）")

for label, translucent in (("一般視窗", False), ("半透明視窗", True)):
    w = W(translucent, f)
    w.show()
    app.processEvents()
    r, n = colored_ratio(w.grab().toImage())
    print(f"  {label:<18} 彩色像素 {r:5.1f}%  （墨跡 {n}）")
    w.hide()

print("\n不同 hinting 對筆畫的影響（不透明目標，看墨跡總量與分布）：")
for name, hint in (("完整 hinting", QFont.PreferFullHinting),
                   ("垂直 hinting", QFont.PreferVerticalHinting),
                   ("不 hinting", QFont.PreferNoHinting),
                   ("預設", QFont.PreferDefaultHinting)):
    pm = QPixmap(360, 36)
    draw(pm, make_font(hint=hint))
    r, n = colored_ratio(pm.toImage())
    print(f"  {name:<14} 彩色 {r:5.1f}%  墨跡 {n}")

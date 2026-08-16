# -*- coding: utf-8 -*-
"""產生 README 功能區塊的四個圖示。

## 為什麼自己畫，不用現成圖示集

這個專案沒有一張外來的圖，杯子、臉、火焰、環全部是程式畫出來的。
插一組 Material 或 emoji 進來，風格會立刻斷掉。

## 為什麼不直接截程式畫面

前兩個概念（島藏在螢幕上緣、點一下就記錄）在 onboard.IslandPreview 裡演過，
但那張圖是 464x150 的橫幅，縮到四欄的寬度只剩 58px 高，藥丸連形狀都看不出來。
圖示要的是輪廓不是實景，所以重畫成正方形的符號。

火焰是例外：stats_window.Flame._path() 就是紀錄視窗裡那把火的形狀，
直接重用同一條路徑，連續天數的圖示與程式裡看到的是同一個東西。

## 顏色

取 theme.DARK 的語意色。那組是校準在深色底上的，但它們同時也夠深，
放在 GitHub 的淺色主題上一樣讀得到；反過來拿 LIGHT 那組（壓深過的）
放到深色底上就會糊掉。README 兩種主題都要能看。

用法：python tools/make_feature_icons.py
"""
import os
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import stats_window as sw  # noqa: E402
import theme  # noqa: E402

OUT = os.path.join(ROOT, "docs")
S = 256                      # 畫布邊長。輸出 2 倍給高解析螢幕，README 顯示約一半
P = theme.DARK

ACCENT = QColor(P.accent)
GREEN = QColor(P.green)
FLAME = QColor(P.flame)
FLAME2 = QColor(P.flame2)
# 結構線用中灰。純黑在深色主題上消失，純白在淺色主題上消失，中灰兩邊都活。
LINE = QColor("#8A8B95")


def canvas():
    img = QImage(S, S, QImage.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    return img, p


def hidden():
    """一台螢幕，藥丸從上緣探進來一半。"""
    img, p = canvas()
    p.setPen(QPen(LINE, 9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(34, 74, 188, 134), 16, 16)
    # 藥丸壓在螢幕上緣，一半在外面：位置關係本身就是這個功能的說明
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRoundedRect(QRectF(94, 56, 68, 36), 18, 18)
    p.end()
    return img


def one_tap():
    """藥丸加游標，右下角一個打勾。"""
    img, p = canvas()
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawRoundedRect(QRectF(38, 92, 150, 56), 28, 28)

    cur = QPainterPath()
    cur.moveTo(120, 128)
    cur.lineTo(120, 196)
    cur.lineTo(139, 178)
    cur.lineTo(152, 205)
    cur.lineTo(167, 198)
    cur.lineTo(154, 172)
    cur.lineTo(179, 169)
    cur.closeSubpath()
    p.setBrush(QColor(255, 255, 255))
    p.setPen(QPen(QColor(40, 42, 50), 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(cur)

    p.setPen(QPen(GREEN, 14, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPolyline([QPointF(186, 76), QPointF(203, 94), QPointF(236, 52)])
    p.end()
    return img


def streak():
    """紀錄視窗那把火，同一條路徑。"""
    img, p = canvas()
    path = sw.Flame._path(S / 2, 214, 168)
    g = QLinearGradient(0, 214 - 168, 0, 214)
    g.setColorAt(0.0, FLAME2)
    g.setColorAt(1.0, FLAME)
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawPath(path)
    p.end()
    return img


def rhythm():
    """時鐘，指針指向深夜。"""
    img, p = canvas()
    p.setPen(QPen(LINE, 9, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF(46, 46, 164, 164))
    p.setPen(QPen(ACCENT, 11, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(128, 128), QPointF(128, 74))       # 分針指向 12
    p.drawLine(QPointF(128, 128), QPointF(170, 152))      # 時針指向 4
    p.setPen(Qt.NoPen)
    p.setBrush(ACCENT)
    p.drawEllipse(QRectF(119, 119, 18, 18))
    p.end()
    return img


ICONS = [("feat-hidden.png", hidden), ("feat-tap.png", one_tap),
         ("feat-streak.png", streak), ("feat-rhythm.png", rhythm)]


def main():
    app = QApplication.instance() or QApplication(sys.argv)   # noqa: F841
    os.makedirs(OUT, exist_ok=True)
    for name, fn in ICONS:
        path = os.path.join(OUT, name)
        if not fn().save(path):
            print(f"FAIL 寫不出 {path}")
            return 1
        print(f"  {name:<18} {os.path.getsize(path) / 1024:>5.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

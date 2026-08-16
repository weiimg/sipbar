# -*- coding: utf-8 -*-
"""像素風表情的比較圖：兩種做法 × 五個狀態 × 兩種尺寸。

A. Lottie 向量杯 + Qt 像素表情
B. 整杯都是像素（不需要 rlottie）

用 Qt 畫，跟島實際的繪製路徑一樣——用 PIL 比出來的結論在正式環境不一定成立。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor, QFont, QImage, QPainter, QPen,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

import pixelface as pf  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
app = QApplication(sys.argv)

PILL = QColor(22, 23, 27)
INK = QColor(235, 235, 245)
GLASS = QColor(206, 212, 224)
WATER = QColor("#4FA8E8")
# 狀態 -> (水位, 表情, 標籤)。水位就是規劃第十六節那張表
STATES = [
    (1.00, pf.NORMAL, "正常"),
    (0.70, pf.THIRSTY, "口渴"),
    (0.35, pf.WEAK, "虛弱"),
    (0.00, pf.COLLAPSED, "倒地"),
    (1.00, pf.SATISFIED, "達標"),
]
WATER_BY_STATE = {pf.COLLAPSED: QColor(120, 122, 130), pf.SATISFIED: QColor("#4FCF8A")}


def lottie_cup(size, level):
    """A 案：向量杯。用 Phase 0 建的線性素材，查表拿到對應的幀。"""
    from rlottie_python import LottieAnimation
    with open(os.path.join(HERE, "water_linear.json"), encoding="utf-8") as f:
        anim = LottieAnimation.from_data(f.read())
    total = anim.lottie_animation_get_totalframe()
    if total <= 0:
        raise ValueError("Lottie 載入失敗")
    frame = int(round((1.0 - level) * (total - 1)))
    buf = anim.lottie_animation_render(frame_num=frame, width=size, height=size)
    return QImage(buf, size, size, size * 4, QImage.Format_ARGB32_Premultiplied).copy()


def render(box, scale, path):
    cols, rows = len(STATES), 2
    cellw = box * scale + 40
    cellh = box * scale + 56
    img = QImage(40 + cols * cellw, 40 + rows * cellh, QImage.Format_ARGB32)
    img.fill(PILL)
    p = QPainter(img)
    f = QFont("Noto Sans TC")
    f.setPixelSize(15)

    for row, mode in enumerate(("A　Lottie 杯 + 像素表情", "B　整杯像素")):
        for col, (level, state, label) in enumerate(STATES):
            x = 40 + col * cellw
            y = 40 + row * cellh
            water = WATER_BY_STATE.get(state, WATER)

            if row == 0:
                cup = lottie_cup(box, level)
                big = cup.scaled(box * scale, box * scale, Qt.KeepAspectRatio,
                                 Qt.FastTransformation)
                p.drawImage(x, y, big)
                # 表情疊在向量杯上，格子大小由放大後的尺寸決定
                p.setRenderHint(QPainter.Antialiasing, False)
                pf.draw(p, x + box * scale / 2, y + box * scale * 0.42,
                        box * scale * 0.46, state, INK)
            else:
                p.setRenderHint(QPainter.Antialiasing, False)
                pf.draw_cup(p, x + box * scale / 2, y + box * scale / 2,
                            level, state, GLASS, water, INK,
                            cell=max(1, int(box * scale // pf.CUP_H)))

            p.setRenderHint(QPainter.Antialiasing, True)
            p.setFont(f)
            p.setPen(QPen(QColor(226, 226, 232)))
            p.drawText(QRect(x, y + box * scale + 8, cellw - 40, 22),
                       Qt.AlignLeft, f"{label}　水位 {level*100:.0f}%")
        p.setPen(QPen(QColor(160, 162, 172)))
        p.drawText(QRect(8, 40 + row * cellh - 26, 400, 22), Qt.AlignLeft, mode)

    p.end()
    img.save(path)
    return path


print("展開尺寸（60px，放大 4 倍看格子）：", render(60, 4, os.path.join(HERE, "pixelface_60.png")))
print("收合尺寸（22px，放大 8 倍）：", render(22, 8, os.path.join(HERE, "pixelface_22.png")))

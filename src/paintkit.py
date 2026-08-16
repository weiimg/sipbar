# -*- coding: utf-8 -*-
"""共用的繪製工具。目前只有柔和陰影。"""

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor


def shadow_alphas(radius, peak, sigma):
    """把想要的高斯衰減反推成每一層該用的 alpha。

    疊層畫陰影時，距離 d 的最終不透明度是所有 i>=d 的層累積起來的：

        A(d) = 1 - Π(1 - a_i)

    所以要得到指定的 A(d)，每一層的 alpha 是

        a_d = 1 - (1 - A(d)) / (1 - A(d+1))

    每層給相同的 alpha 會得到線性衰減——邊緣是硬的、還看得出一圈一圈的階梯。
    那正是「陰影不夠柔和、沒有羽化」的原因。高斯衰減在外側的增量極小，
    階梯就消失了。

    這串係數只跟參數有關，模組載入時算一次就好。
    """
    def A(d):
        return peak * math.exp(-(d * d) / (2.0 * sigma * sigma))

    out = [0.0] * (radius + 2)
    for d in range(radius, 0, -1):
        den = 1.0 - A(d + 1)
        out[d] = max(0.0, 1.0 - (1.0 - A(d)) / den) if den > 1e-6 else 0.0
    return out


def draw_soft_shadow(p, rect, alphas, offset_y=0.0, corner=None, color=(0, 0, 0)):
    """沿著 rect 的外圍疊出高斯衰減的陰影。

    corner=None 代表膠囊形（圓角半徑＝高度的一半），否則用指定的固定半徑。
    """
    p.setPen(Qt.NoPen)
    r, g, b = color
    for d in range(len(alphas) - 2, 0, -1):
        a = alphas[d]
        if a <= 0.0008:
            continue
        s = QRectF(rect.left() - d, rect.top() - d + offset_y,
                   rect.width() + d * 2, rect.height() + d * 2)
        rad = s.height() / 2 if corner is None else corner + d
        p.setBrush(QColor(r, g, b, max(1, int(round(a * 255)))))
        p.drawRoundedRect(s, rad, rad)

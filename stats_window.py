# -*- coding: utf-8 -*-
"""喝水紀錄視窗。

## 為什麼用版面引擎而不是自己算座標

前幾版把每個元素的位置寫成 paintEvent 裡的魔術數字（`top + 88`、`cy - 12`…），
結果是同一類 bug 一直重複出現：卡片高度用猜的所以內容被切掉、對齊靠巧合所以
出現三條左緣、字級一改整張版面就跑掉。

改成：**結構交給 Qt 的 layout，文字交給 QLabel，只有真正的圖形（環、火焰、護盾、
熱力圖、進度條）才自繪。** 於是——

- 卡片高度由內容決定（`sizeHint`），不可能再切到內容
- 間距與內距宣告一次（`PAD` / `GAP` / `S*`），不是每處各挑一個數字
- 換字級會自動重排，不用手動重算幾十個偏移
- 對齊是結構性的：同一個 layout 的子元件本來就對齊

## 其他規則（前幾版踩出來的）

- 值得常駐顯示的資訊就配得上 14px，配不上的就進 tooltip。介面不解釋自己的機制。
- 虛線不用來表示「還沒發生」——虛線在介面慣例裡代表錯誤或佔位。
- 半透明視窗只能用灰階抗鋸齒，不能照抄蘋果 60% 不透明度的次要文字規格。

資料計算在 dashboard.py，這裡只負責呈現。
"""

import math
import os
import subprocess
import time
from datetime import datetime, timedelta

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QIntValidator, QLinearGradient,
    QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QApplication, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit,
    QSizePolicy, QStackedWidget, QToolTip, QVBoxLayout, QWidget,
)

import dashboard
import settings as appsettings               # 設定的讀寫與推導
import typeface                               # 隨程式散布的字體
from motion import PRESET, Spring, clamp, ease, lerp
from paintkit import draw_soft_shadow, shadow_alphas

# ---------------------------------------------------------------- 設計常數

# 字型：Noto Sans TC 而非 Microsoft JhengHei UI。
#
# 實測（scratchpad/compare_engines.py）比較過 default / freetype / gdi 三種字型引擎
# 與三種字型：JhengHei UI 的 Regular 筆畫太細，淺色字放深色底上會因為 gamma 更顯薄；
# Noto Sans TC 筆畫厚實、字形乾淨，小字尤其明顯。
#
# 關鍵差別是字重：Noto Sans TC 有真正的 Medium 500（exactMatch），
# JhengHei UI 只有 Regular / Light / Bold，要求 Medium 會退回 400——
# 沒有中間值可以補償深色底的視覺變細。
# 內文一律用 Medium 而非 Regular，就是這個補償。
#
# 字體檔已隨程式散布（assets/fonts/），載入與驗證見 typeface.py——
# 以前這裡假設機器上裝了它，那對自用成立，發布出去就不成立。
# 這個常數留著只為了 tests/font_ab.py 可以換字體做 A/B 比對。
FONT = typeface.FAMILY

# caption 15 是最小字級的地板。實測（scratchpad/small_text.py）比較過 14px 的
# hinting 變體、加粗、提高對比——都沒用：14px 時「續／積／補／標」這類筆畫密的字
# 會整團糊在一起，加粗反而更糟。**中文小字的瓶頸是像素數，不是字重或對比。**
# 15px 開始筆畫才分得開。
TYPE = {                       # 角色 -> (px, 字重, 字距)
    "display":  (64, QFont.Bold, -1.6),
    "title":    (28, QFont.Bold, -0.5),
    "section":  (20, QFont.Bold, -0.2),
    "headline": (18, QFont.Bold, 0.0),
    "body":     (17, QFont.Medium, 0.0),
    "caption":  (15, QFont.Medium, 0.0),
}

S1, S2, S3, S4, S5 = 4, 8, 16, 24, 32     # 間距級距，只用 4 的倍數
PAD = 24                                   # 卡片內距
GAP = 16                                   # 卡片之間
SHADOW = 30                                # 視窗投影留白
SHADOW_SIGMA = 11.0
SHADOW_PEAK = 0.34
SHADOW_OFFSET_Y = 7
SHADOW_ALPHAS = shadow_alphas(SHADOW - 2, SHADOW_PEAK, SHADOW_SIGMA)
# 高度不寫死：視窗會自己收到「最高那一頁」剛好放得下（見 _fit_height）。
# 這裡的 WIN_H 只是還沒量到內容之前的暫定值。
WIN_W, WIN_H = 780, 900
WIN_PAD = 32                               # 視窗內距

INK = "rgba(245,245,247,1)"
INK2 = "rgba(235,235,245,0.84)"
INK3 = "rgba(235,235,245,0.74)"
C_ACCENT = QColor("#4FA8E8")
C_GREEN = QColor("#4FCF8A")
C_FLAME = QColor("#FF9F43")
C_FLAME2 = QColor("#FFD166")
C_DANGER = "rgba(232,122,79,1)"             # 破壞性動作，跟「虛弱」狀態同一個橘紅
C_SLOT = QColor(255, 255, 255, 24)
C_CARD_TOP = QColor(34, 35, 41)
C_CARD_BOTTOM = QColor(23, 24, 29)
C_BG_TOP = QColor(28, 29, 34, 252)
C_BG_BOTTOM = QColor(14, 15, 18, 252)

STAGGER_MS = 62
WEEKDAYS = "一二三四五六日"
GEAR_GAP = 40                              # 齒輪中心離關閉鈕中心多遠

_FONTS = {}


def font(role):
    f = _FONTS.get(role)
    if f is None:
        px, weight, tracking = TYPE[role]
        f = typeface.make(px, weight, tracking, family=FONT)
        _FONTS[role] = f
    return f


class Label(QLabel):
    """過長就用省略號，不會被硬切掉半個字。"""

    def __init__(self, text="", role="body", color=INK2, elide=False):
        super().__init__(text)
        self._full = text
        self._elide = elide
        self.setFont(font(role))
        self.setStyleSheet(f"color:{color};background:transparent")
        self.setAttribute(Qt.WA_TranslucentBackground)
        if elide:
            self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def setText(self, text):
        self._full = text
        super().setText(text)

    def paintEvent(self, event):
        if not self._elide:
            return super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        fm = QFontMetrics(self.font())
        p.setPen(self.palette().color(self.foregroundRole()))
        p.setFont(self.font())
        shown = fm.elidedText(self._full, Qt.ElideRight, self.width())
        p.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter, shown)


def para(text, role="caption", color=INK3):
    """會換行的整段說明。

    Label 的省略號是給「一行放不下就切掉」的欄位用的——那適合數值旁邊的短註解，
    不適合成段的說明：一段話被切成「…程式看你的活動紀…」等於完全沒說。
    需要讀完的文字就要換行，能捨棄的才用省略號。
    """
    lbl = QLabel(text)
    lbl.setFont(font(role))
    lbl.setStyleSheet(f"color:{color};background:transparent")
    lbl.setAttribute(Qt.WA_TranslucentBackground)
    lbl.setWordWrap(True)
    lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    return lbl


class CountLabel(Label):
    """數字從 0 跳到目標值。寬度先鎖在最終值，否則數字變長會把旁邊的字推來推去。"""

    def __init__(self, value, role="display", color=INK):
        super().__init__(str(value), role, color)
        self.value = value
        self.setMinimumWidth(QFontMetrics(font(role)).horizontalAdvance(str(value)))

    def set_reveal(self, t):
        self.setText(str(int(round(self.value * ease(clamp(t, 0.0, 1.0))))))


def _fill(lay, items, align=None):
    """items 可放 widget、"stretch"、int（間距）、或 (widget, 伸展因子)。

    需要吃掉剩餘空間的欄位要給伸展因子，不能靠旁邊放一個 "stretch"——
    那會讓彈簧把空間搶走，會省略的文字就被壓成「一天內補…」。
    """
    for it in items:
        if isinstance(it, tuple):
            w, stretch = it
            lay.addWidget(w, stretch)
        elif it == "stretch":
            lay.addStretch(1)
        elif isinstance(it, int):
            lay.addSpacing(it)
        elif align is not None:
            lay.addWidget(it, 0, align)
        else:
            lay.addWidget(it)


def row(*items, spacing=S2, margins=(0, 0, 0, 0), align=None):
    w = QWidget()
    w.setAttribute(Qt.WA_TranslucentBackground)
    lay = QHBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    _fill(lay, items, align)
    return w


def col(*items, spacing=S1, margins=(0, 0, 0, 0), align=None):
    w = QWidget()
    w.setAttribute(Qt.WA_TranslucentBackground)
    lay = QVBoxLayout(w)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    _fill(lay, items, align)
    return w


# ---------------------------------------------------------------- 圖形元件

class Graphic(QWidget):
    """自繪的葉節點。reveal 由卡片統一餵進來驅動內部的值動畫。"""

    def __init__(self, w=None, h=None):
        super().__init__()
        self.reveal = 1.0
        self.setAttribute(Qt.WA_TranslucentBackground)
        if w is not None:
            self.setFixedWidth(w)
        if h is not None:
            self.setFixedHeight(h)

    def set_reveal(self, t):
        self.reveal = t
        self.update()


class Ring(Graphic):
    def __init__(self, value, target, size=132):
        super().__init__(size, size)
        self.value = value
        self.target = target

    def paintEvent(self, event):
        """達標顯示打勾、未達標顯示數字——跟週曆那排圓圈用同一套語彙。

        不放「7 / 7」：環滿了本身就是「達標」，再寫一次分數是重複資訊；
        而且分母獨立成一行時會讀成半截分數。目標值由狀態列與視窗副標負責交代。
        """
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        e = ease(self.reveal)
        r = self.width() / 2 - 6
        cx = cy = self.width() / 2
        box = QRectF(cx - r, cy - r, r * 2, r * 2)
        done = self.value >= self.target

        p.setPen(QPen(QColor(255, 255, 255, 28), 11))
        p.drawArc(box, 0, 360 * 16)
        pct = min(1.0, self.value / self.target if self.target else 0) * e
        if pct > 0:
            p.setPen(QPen(C_GREEN if done else C_ACCENT, 11, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(box, 90 * 16, -int(360 * 16 * pct))

        if done:
            k = r * 0.42 * lerp(0.6, 1.0, e)
            p.setPen(QPen(C_GREEN, 5.0, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPoint(int(cx - k), int(cy + k * 0.06)),
                       QPoint(int(cx - k * 0.22), int(cy + k * 0.66)))
            p.drawLine(QPoint(int(cx - k * 0.22), int(cy + k * 0.66)),
                       QPoint(int(cx + k), int(cy - k * 0.62)))
            return

        f = font("title")
        fm = QFontMetrics(f)
        num = str(int(round(self.value * e)))
        p.setFont(f)
        p.setPen(QColor(245, 245, 247))
        # 數字沒有下伸部，用 cap height 對齊才是光學置中
        p.drawText(int(cx - fm.horizontalAdvance(num) / 2),
                   int(round(cy + fm.capHeight() / 2)), num)


class Flame(Graphic):
    def __init__(self, lit, w=76, h=112):
        super().__init__(w, h)
        self.lit = lit

    @staticmethod
    def _path(cx, bottom, h):
        """對稱的水滴形會讀成葉子：尖端偏一邊、底部鼓出才像火。"""
        w = h * 0.78
        tip_x, tip_y = cx - w * 0.10, bottom - h
        path = QPainterPath()
        path.moveTo(tip_x, tip_y)
        path.cubicTo(cx + w * 0.30, bottom - h * 0.74,
                     cx + w * 0.52, bottom - h * 0.44,
                     cx + w * 0.38, bottom - h * 0.14)
        path.cubicTo(cx + w * 0.30, bottom + h * 0.03,
                     cx - w * 0.30, bottom + h * 0.03,
                     cx - w * 0.38, bottom - h * 0.14)
        path.cubicTo(cx - w * 0.54, bottom - h * 0.46,
                     cx - w * 0.16, bottom - h * 0.60,
                     tip_x, tip_y)
        return path

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        h = (self.height() - 6) * lerp(0.74, 1.0, ease(self.reveal))
        cx, bottom = self.width() / 2, self.height() - 3
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(C_FLAME if self.lit else C_SLOT))
        p.drawPath(self._path(cx, bottom, h))
        p.setBrush(QBrush(C_FLAME2 if self.lit else QColor(255, 255, 255, 16)))
        p.drawPath(self._path(cx, bottom - h * 0.06, h * 0.56))


class Shields(Graphic):
    STEP, R = 38, 14

    def __init__(self, total, left):
        super().__init__(total * Shields.STEP, Shields.R * 2 + S2)
        self.total = total
        self.left = left
        self.setToolTip(f"未達標時自動抵用，連續不歸零。每月補回 {total} 個。\n"
                        f"目前剩 {left} 個。")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        e = ease(self.reveal)
        y = self.height() / 2
        for i in range(self.total):
            local = ease(clamp((e - 0.4 - i * 0.08) / 0.45, 0.0, 1.0))
            if local <= 0.01:
                continue
            on = i < self.left
            r = self.R * local
            x = self.STEP * (i + 0.5)
            path = QPainterPath()
            path.moveTo(x, y - r)
            path.lineTo(x + r * 0.86, y - r * 0.5)
            path.lineTo(x + r * 0.86, y + r * 0.16)
            path.cubicTo(x + r * 0.86, y + r * 0.82, x + r * 0.42, y + r * 1.06, x, y + r * 1.18)
            path.cubicTo(x - r * 0.42, y + r * 1.06, x - r * 0.86, y + r * 0.82,
                         x - r * 0.86, y + r * 0.16)
            path.lineTo(x - r * 0.86, y - r * 0.5)
            path.closeSubpath()
            p.setPen(QPen(C_ACCENT if on else QColor(255, 255, 255, 46), 2.2))
            p.setBrush(QBrush(QColor(79, 168, 232, 72) if on else Qt.transparent))
            p.drawPath(path)


class WeekStrip(Graphic):
    def __init__(self, days, target):
        super().__init__(None, 112)
        self.days = days
        self.target = target
        self._hit = []
        self.setMouseTracking(True)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        e = ease(self.reveal)
        step = self.width() / 7
        rad = min(32, step / 2 - 12)
        fm_l = QFontMetrics(font("body"))
        fm_n = QFontMetrics(font("headline"))
        self._hit = []

        for i, day in enumerate(self.days):
            local = ease(clamp((e - i * 0.055) / 0.55, 0.0, 1.0))
            if local <= 0.01:
                continue
            cx = step * (i + 0.5)
            cy = self.height() - rad - 6
            r = rad * lerp(0.74, 1.0, local)

            p.setFont(font("body"))
            p.setPen(QColor(245, 245, 247) if day["today"] else QColor(235, 235, 245, 168))
            lw = fm_l.horizontalAdvance(day["label"])
            p.drawText(int(cx - lw / 2), int(fm_l.ascent()) + 2, day["label"])

            p.setPen(Qt.NoPen)
            box = QRectF(cx - r, cy - r, r * 2, r * 2)
            if day["future"]:
                p.setBrush(QBrush(QColor(255, 255, 255, 14)))
                p.drawEllipse(box)
                note = "還沒到"
            elif day["hit"]:
                p.setBrush(QBrush(C_GREEN))
                p.drawEllipse(box)
                p.setPen(QPen(QColor(16, 22, 18), 3.6, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPoint(int(cx - r * 0.34), int(cy + r * 0.02)),
                           QPoint(int(cx - r * 0.08), int(cy + r * 0.28)))
                p.drawLine(QPoint(int(cx - r * 0.08), int(cy + r * 0.28)),
                           QPoint(int(cx + r * 0.36), int(cy - r * 0.26)))
                note = f"{day['drinks']} / {self.target} 次，達標"
            elif day["used"]:
                pct = (day["drinks"] / self.target) * local if self.target else 0
                p.setPen(QPen(QColor(255, 255, 255, 28), 5))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(box)
                if pct > 0:
                    p.setPen(QPen(C_ACCENT, 5, Qt.SolidLine, Qt.RoundCap))
                    p.drawArc(box, 90 * 16, -int(360 * 16 * pct))
                n = str(day["drinks"])
                p.setFont(font("headline"))
                p.setPen(QColor(245, 245, 247))
                p.drawText(int(cx - fm_n.horizontalAdvance(n) / 2),
                           int(cy + fm_n.capHeight() / 2), n)
                note = f"{day['drinks']} / {self.target} 次"
            else:
                p.setBrush(QBrush(C_SLOT))
                p.drawEllipse(box)
                note = "沒開電腦，不計入連續"

            if day["today"]:
                p.setPen(QPen(C_ACCENT, 2))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QRectF(cx - r - 7, cy - r - 7, (r + 7) * 2, (r + 7) * 2))

            self._hit.append((QRectF(cx - rad - 8, cy - rad - 8, (rad + 8) * 2, (rad + 8) * 2),
                              f"{day['key']}　{note}"))

    def mouseMoveEvent(self, event):
        pos = event.position()
        for rect, text in self._hit:
            if rect.contains(pos):
                QToolTip.showText(event.globalPosition().toPoint(), text, self)
                return
        QToolTip.hideText()


class Heatmap(Graphic):
    CGAP, LABEL_W, MAX_CELL = 5, 26, 20

    def __init__(self, data):
        super().__init__(None, None)
        self.data = data
        self._hit = []
        self.setMouseTracking(True)
        self.setFixedHeight(int(7 * (self.MAX_CELL + self.CGAP) - self.CGAP))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        e = ease(self.reveal)
        weeks = dashboard.HEATMAP_WEEKS
        avail = self.width() - self.LABEL_W
        cell = min(self.MAX_CELL, (avail - self.CGAP * (weeks - 1)) / weeks)
        step = cell + self.CGAP
        target = self.data["target"]

        fm = QFontMetrics(font("caption"))
        p.setFont(font("caption"))
        p.setPen(QColor(235, 235, 245, 168))
        for i in range(0, 7, 2):
            p.drawText(0, int(i * step + cell / 2 + fm.capHeight() / 2), WEEKDAYS[i])

        today = datetime.strptime(self.data["today_key"], "%Y-%m-%d")
        start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
        self._hit = []
        p.setPen(Qt.NoPen)
        for w in range(weeks):
            for wd in range(7):
                day = start + timedelta(days=w * 7 + wd)
                if day > today:
                    continue
                local = ease(clamp((e - (w + wd) * 0.014) / 0.45, 0.0, 1.0))
                if local <= 0.01:
                    continue
                key = day.strftime("%Y-%m-%d")
                info = self.data["days"].get(key)
                c = cell * lerp(0.55, 1.0, local)
                off = (cell - c) / 2
                x, y = self.LABEL_W + w * step, wd * step
                p.setBrush(QBrush(self._color(info, target)))
                p.drawRoundedRect(QRectF(x + off, y + off, c, c), 5, 5)

                n = info["drinks"] if info else 0
                if key in self.data["streak"]["saved_days"]:
                    note = f"{n} / {target} 次，護盾抵用"
                elif info and (info["drinks"] or info["reminds"]):
                    note = f"{n} / {target} 次"
                else:
                    note = "沒開電腦，不計入連續"
                self._hit.append((QRectF(x, y, cell, cell), f"{key}　{note}"))

    @staticmethod
    def _color(info, target):
        if info is None or (info["drinks"] == 0 and info["reminds"] == 0):
            return C_SLOT                       # 空欄位，不是失敗
        ratio = info["drinks"] / target if target else 0
        if ratio >= 1:
            return C_GREEN
        if ratio >= 0.66:
            return QColor(79, 207, 138, 175)
        if ratio >= 0.33:
            return QColor(79, 168, 232, 160)
        if ratio > 0:
            return QColor(79, 168, 232, 96)
        return QColor(255, 255, 255, 52)

    def mouseMoveEvent(self, event):
        pos = event.position()
        for rect, text in self._hit:
            if rect.contains(pos):
                QToolTip.showText(event.globalPosition().toPoint(), text, self)
                return
        QToolTip.hideText()


class Bar(Graphic):
    def __init__(self, pct, w=96):
        super().__init__(w, 8)
        self.pct = pct

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(255, 255, 255, 26)))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 4, 4)
        v = self.pct * ease(self.reveal)
        if v > 0:
            p.setBrush(QBrush(C_ACCENT))
            p.drawRoundedRect(QRectF(0, 0, max(8, self.width() * v), self.height()), 4, 4)


class Badge(Graphic):
    def __init__(self, done, remain, size=44):
        super().__init__(size, size)
        self.done = done
        self.remain = remain

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        r = self.width() / 2 * lerp(0.82, 1.0, ease(self.reveal))
        cx = cy = self.width() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(79, 168, 232, 66) if self.done else QColor(255, 255, 255, 18)))
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        if self.done:
            p.setPen(QPen(C_ACCENT, 3.4, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPoint(int(cx - 8), int(cy + 1)), QPoint(int(cx - 2), int(cy + 7)))
            p.drawLine(QPoint(int(cx - 2), int(cy + 7)), QPoint(int(cx + 9), int(cy - 7)))
        else:
            f = font("headline")
            fm = QFontMetrics(f)
            t = str(self.remain)
            p.setFont(f)
            p.setPen(QColor(235, 235, 245, 168))
            p.drawText(int(cx - fm.horizontalAdvance(t) / 2), int(cy + fm.capHeight() / 2), t)


def stat_block(value, label):
    return col(Label(value, "title", INK), Label(label, "caption", INK3), spacing=S1)


# ---------------------------------------------------------------- 卡片

class Card(QWidget):
    """背景自繪，內容全部交給 layout——高度由內容決定，不再是手算的常數。"""

    def __init__(self, title=None):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.sp = Spring(0.0, *PRESET["enter"])
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)

        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(PAD, PAD, PAD, PAD)
        self.box.setSpacing(S3)
        if title:
            self.box.addWidget(Label(title, "section", INK2))

    def add(self, *widgets, spacing=None):
        for w in widgets:
            if isinstance(w, int):
                self.box.addSpacing(w)
            else:
                self.box.addWidget(w)
        if spacing is not None:
            self.box.setSpacing(spacing)

    def set_reveal(self, t):
        """任何有 set_reveal 的子元件都跟著動，不限自繪的圖形。"""
        self._fx.setOpacity(clamp(ease(t), 0.0, 1.0))
        for w in self.findChildren(QWidget):
            if w is not self and hasattr(w, "set_reveal"):
                w.set_reveal(t)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0.0, C_CARD_TOP)
        g.setColorAt(1.0, C_CARD_BOTTOM)
        p.setPen(QPen(QColor(255, 255, 255, 20), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 20, 20)
        hl = QLinearGradient(0, 0, 0, self.height() * 0.5)
        hl.setColorAt(0.0, QColor(255, 255, 255, 26))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QBrush(hl), 1.0))
        p.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 19, 19)


def build_streak_card(d):
    t, today, streak = d["target"], d["today"]["drinks"], d["streak"]["streak"]
    s = d["streak"]
    left = t - today
    if today >= t:
        status = "今天已達標"
    elif streak > 0:
        status = f"再 {left} 次維持連續"
    elif today > 0:
        status = f"還差 {left} 次達標"
    else:
        status = "今天還沒開始"

    num = CountLabel(streak, "display", INK if streak else INK3)
    ring = Ring(today, t)
    ring.setToolTip(f"今天 {today} / {t} 次")

    card = Card()
    card.add(
        row(Flame(streak > 0),
            (col(row(num, Label("天", "section", INK2), "stretch", spacing=S2),
                 Label("連續達標", "caption", INK3),
                 spacing=S1), 1),
            ring,
            spacing=S3),
        Label(status, "body", INK2, elide=True),
        row(Label("護盾", "caption", INK3), Shields(s["saves_total"], s["saves_left"]),
            "stretch", spacing=S3),
    )
    return card


def build_week_card(d):
    card = Card("本週")
    card.add(WeekStrip(dashboard.week_days(d), d["target"]))
    return card


def build_trail_card(d):
    card = Card("紀錄")
    card.add(
        Heatmap(d),
        row(stat_block(str(d["longest"]), "最長連續（天）"),
            "stretch",
            stat_block(str(d["total_drinks"]), "累積補水（次）"),
            "stretch",
            stat_block(f"{d['total_drinks'] * d['ml'] / 1000:.1f}", "估算水量（公升）"),
            spacing=S3),
    )
    return card


def build_achievements_card(d):
    card = Card("成就")
    card.box.setSpacing(S2)
    for name, desc, cur, goal in dashboard.achievements(d):
        done = cur >= goal
        card.add(row(
            Badge(done, goal - cur),
            (col(Label(name, "headline", INK if done else INK2),
                 Label(desc, "caption", INK3, elide=True),
                 spacing=S1), 1),          # 文字欄位吃掉剩餘空間
            col(Bar(cur / goal if goal else 0),
                Label("完成" if done else f"{cur} / {goal}", "caption",
                      INK2 if done else INK3),
                spacing=S1, align=Qt.AlignHCenter),
            spacing=S3))
    return card


def build_footer_card(d):
    rate = f"{d['rate'] * 100:.0f}%" if d["rate"] is not None else "—"
    wait = f"{d['avg_wait_min']:.0f} 分" if d["avg_wait_min"] is not None else "—"
    card = Card()
    card.add(row(stat_block(rate, "提醒回應率"), "stretch",
                 stat_block(wait, "平均回應時間"), "stretch", spacing=S3))
    return card


# 分頁切法：每頁要有一個主角。一頁塞兩個同等重要的東西，等於沒有重點。
PAGES = [
    ("今天", [build_streak_card, build_week_card]),
    ("紀錄", [build_trail_card, build_footer_card]),
    ("成就", [build_achievements_card]),
]


class Segmented(QWidget):
    """分段控制項。分頁用它切換，不用側邊欄。

    760 寬的視窗橫向是稀缺資源、縱向不是：側邊欄要吃 140px（18% 的寬度），
    分段控制項只吃 40px 高。而且三個項目的側邊欄看起來是空的——
    側邊欄要到六項以上、或有階層時才划算。
    """

    changed = Signal(int)

    H = 40
    INSET = 4

    def __init__(self, labels):
        super().__init__()
        self.labels = labels
        self.index = 0
        self.setFixedHeight(self.H)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.PointingHandCursor)
        # 選取的藥丸用彈簧滑過去，不是瞬間跳——跟島同一套物理
        self.sp = Spring(0.0, 0.38, 0.85)
        self._f = font("headline")
        self.frame = QTimer(self)
        self.frame.setInterval(16)
        self.frame.timeout.connect(self._step)
        self._last = time.perf_counter()

    def seg_w(self):
        return (self.width() - self.INSET * 2) / max(1, len(self.labels))

    def set_index(self, i, animate=True):
        if i == self.index:
            return
        self.index = i
        self.sp.target = float(i)
        if animate:
            if not self.frame.isActive():
                self._last = time.perf_counter()
                self.frame.start()
        else:
            self.sp.snap(float(i))
        self.update()
        self.changed.emit(i)

    def _step(self):
        now = time.perf_counter()
        self.sp.step(now - self._last)
        self._last = now
        if self.sp.settled:
            self.sp.snap(self.sp.target)
            self.frame.stop()
        self.update()

    def mousePressEvent(self, event):
        self.set_index(int(clamp((event.position().x() - self.INSET) // self.seg_w(),
                                 0, len(self.labels) - 1)))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setPen(Qt.NoPen)

        p.setBrush(QColor(235, 235, 245, 20))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.H), self.H / 2, self.H / 2)

        w = self.seg_w()
        pill = QRectF(self.INSET + self.sp.value * w, self.INSET, w, self.H - self.INSET * 2)
        p.setBrush(QColor(235, 235, 245, 34))
        p.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)

        fm = QFontMetrics(self._f)
        p.setFont(self._f)
        baseline = int(round(self.H / 2 + (fm.ascent() - fm.descent()) / 2))
        for i, text in enumerate(self.labels):
            # 亮度跟著彈簧的距離插值，切換時是滑過去而不是瞬間換色
            near = clamp(1.0 - abs(self.sp.value - i), 0.0, 1.0)
            p.setPen(QColor(235, 235, 245, int(lerp(150, 255, near))))
            cx = self.INSET + w * (i + 0.5)
            p.drawText(int(cx - fm.horizontalAdvance(text) / 2), baseline, text)


# ---------------------------------------------------------------- 設定頁的元件

class Toggle(Graphic):
    """開關。用彈簧滑過去，跟島與分段控制項同一套物理。

    不用 QCheckBox：勾選框在這張版面裡是唯一一個「作業系統長相」的東西，
    而且它不會動——旁邊每個元件都有彈簧，只有它瞬間跳，會很突兀。
    """

    toggled = Signal(bool)

    W, H = 52, 32

    def __init__(self, on=False):
        super().__init__(self.W, self.H)
        self.on = on
        self.setCursor(Qt.PointingHandCursor)
        self.sp = Spring(1.0 if on else 0.0, 0.34, 0.82)
        self.frame = QTimer(self)
        self.frame.setInterval(16)
        self.frame.timeout.connect(self._step)
        self._last = time.perf_counter()

    def set_on(self, on, animate=True, emit=True):
        if on == self.on:
            return
        self.on = on
        self.sp.target = 1.0 if on else 0.0
        if animate:
            if not self.frame.isActive():
                self._last = time.perf_counter()
                self.frame.start()
        else:
            self.sp.snap(self.sp.target)
        self.update()
        if emit:
            self.toggled.emit(on)

    def _step(self):
        now = time.perf_counter()
        self.sp.step(now - self._last)
        self._last = now
        if self.sp.settled:
            self.sp.snap(self.sp.target)
            self.frame.stop()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.set_on(not self.on)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setOpacity(clamp(ease(self.reveal), 0.0, 1.0))
        t = clamp(self.sp.value, 0.0, 1.0)

        track = QRectF(0, 0, self.W, self.H)
        off = QColor(235, 235, 245, 30)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(int(lerp(off.red(), C_GREEN.red(), t)),
                          int(lerp(off.green(), C_GREEN.green(), t)),
                          int(lerp(off.blue(), C_GREEN.blue(), t)),
                          int(lerp(off.alpha(), 255, t))))
        p.drawRoundedRect(track, self.H / 2, self.H / 2)

        r = self.H / 2 - 4
        cx = lerp(4 + r, self.W - 4 - r, t)
        p.setBrush(QColor(255, 255, 255, 240))
        p.drawEllipse(QRectF(cx - r, self.H / 2 - r, r * 2, r * 2))


class TapLabel(Label):
    """可以點的文字。給「開啟資料夾」「清除所有資料」這種次要動作用。

    不用 QPushButton：按鈕在這張版面裡會帶進一整套作業系統的外觀，
    要用 stylesheet 蓋掉的東西比自己畫還多。
    """

    clicked = Signal()

    def __init__(self, text, color=INK2):
        super().__init__(text, "body", color)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


class WeightField(QLineEdit):
    """體重輸入。留空代表不指定，用預設次數。

    這是整個視窗唯一的文字輸入框，所以得把作業系統的外觀整個蓋掉，
    才不會在一片自繪的卡片中間開一個 Windows 的洞。
    """

    def __init__(self, value):
        super().__init__("" if not value else str(int(value)))
        self.setValidator(QIntValidator(30, 200, self))
        self.setPlaceholderText("選填")
        self.setAlignment(Qt.AlignRight)
        self.setFixedSize(78, 38)     # 高度也要釘住，否則會被列高拉長
        self.setFont(font("body"))
        self.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(255,255,255,0.07);
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 9px;
                padding: 6px 10px;
                color: {INK};
                selection-background-color: rgba(79,168,232,0.5);
            }}
            QLineEdit:focus {{ border: 1px solid rgba(79,168,232,0.85); }}
        """)

    def value(self):
        try:
            return int(self.text())
        except ValueError:
            return None


# ---------------------------------------------------------------- 設定頁的網格
#
# 縱向以 8px 為基線，橫向切成兩欄。設定列之所以會看起來「沒排好」，多半不是
# 對齊錯了，是**每一列的高度都不一樣**——有說明的列自己長高、沒說明的列自己縮短，
# 於是右側控制項的中心線每一列都落在不同的地方，眼睛掃下來就是歪的。
#
# 解法是把列高釘死成兩種，兩種都是 8 的倍數，控制項一律垂直置中。

GRID = 8
ROW_TALL = GRID * 6        # 48：有說明的設定列（標題 + 說明兩行）
ROW_FLAT = GRID * 5        # 40：單行的設定列。裡面有控制項，要留得下點擊區
ROW_INFO = GRID * 4        # 32：唯讀資訊列。沒有東西要點，就不需要那個餘裕——
                           #     互動列比資訊列高，是因為手指與滑鼠需要空間，不是為了好看
ROW_SECTION = GRID * 3     # 24：區塊標題
LABEL_RATIO = 0.56         # 標籤欄佔的寬度；其餘留給控制項，右對齊
C_DIVIDER = QColor(255, 255, 255, 20)


class Divider(QWidget):
    """1px 分隔線。用來切開語意不同的區塊，比拉大間距明確。"""

    def __init__(self, inset=0):
        super().__init__()
        self.inset = inset
        self.setFixedHeight(1)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.inset, 0, self.width() - self.inset * 2, 1, C_DIVIDER)


def section_header(text, note=None):
    """區塊標題。比卡片標題小一級，用來在同一張卡裡分段。

    高度一樣要釘死。區塊標題若讓內容決定高度，它就會是整份清單裡
    唯一不在基線上的東西——而那正是「看起來沒排好」最常見的來源。
    """
    items = [Label(text, "caption", INK3)]
    if note:
        items += ["stretch", Label(note, "caption", INK3)]
    w = row(*items, spacing=S2, align=Qt.AlignVCenter)
    w.setFixedHeight(ROW_SECTION)
    return w


def setting_row(label, control, hint=None):
    """一列設定：左欄標題（可帶說明），右欄控制項，右對齊、垂直置中。

    **列高釘死**，不讓內容決定——有說明的 48、沒說明的 40。
    高度浮動的話，右側控制項的中心線會每列不同，整欄看起來是歪的。

    左欄用伸展因子吃掉剩餘寬度，不是在旁邊塞 "stretch"：
    那會讓 stretch 把空間搶走，帶省略號的說明被壓成「這是在電腦…」。
    """
    left = col(Label(label, "headline", INK),
               *([Label(hint, "caption", INK3, elide=True)] if hint else []),
               spacing=2)
    w = row((left, 1), control, spacing=S3, align=Qt.AlignVCenter)
    w.setFixedHeight(ROW_TALL if hint else ROW_FLAT)
    return w


def info_row(label, value, trailing=None):
    """唯讀資訊列：左邊名稱、右邊值，值太長就省略。跟設定列共用同一條基線。"""
    items = [Label(label, "body", INK3),
             (Label(value, "body", INK2, elide=True), 1)]
    if trailing is not None:
        items.append(trailing)
    w = row(*items, spacing=S3, align=Qt.AlignVCenter)
    w.setFixedHeight(ROW_INFO)
    return w


class DangerAction(QWidget):
    """破壞性動作：點一下先進入確認狀態，就地問「確定要刪除嗎？」。

    不用系統對話框，兩個理由：
    一是 QMessageBox 會在這片自繪的深色版面中間開一個 Windows 的洞；
    二是對話框會蓋住使用者正要刪的東西，人看不到自己在刪什麼。

    確認狀態會自己收回去。留著一顆armed 的刪除鍵在畫面上，
    下一次不小心點到就真的刪了。
    """

    confirmed = Signal()

    REVERT_MS = 8000

    def __init__(self, label, prompt, confirm_text="刪除"):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedHeight(ROW_FLAT)
        self._armed = False

        self.idle_lbl = Label(label, "caption", INK3, elide=True)
        self.action = TapLabel("清除紀錄", C_DANGER)
        self.action.clicked.connect(self._arm)

        self.prompt_lbl = Label(prompt, "body", INK)
        self.cancel = TapLabel("取消", INK2)
        self.cancel.clicked.connect(self._disarm)
        self.confirm = TapLabel(confirm_text, C_DANGER)
        self.confirm.clicked.connect(self._fire)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(S3)
        lay.addWidget(self.idle_lbl, 1)
        lay.addWidget(self.prompt_lbl, 1)
        lay.addWidget(self.cancel)
        lay.addWidget(self.action)
        lay.addWidget(self.confirm)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._disarm)
        self._sync()

    def _sync(self):
        self.idle_lbl.setVisible(not self._armed)
        self.action.setVisible(not self._armed)
        self.prompt_lbl.setVisible(self._armed)
        self.cancel.setVisible(self._armed)
        self.confirm.setVisible(self._armed)

    def _arm(self):
        self._armed = True
        self._sync()
        self._timer.start(self.REVERT_MS)

    def _disarm(self):
        self._timer.stop()
        self._armed = False
        self._sync()

    def _fire(self):
        self._disarm()
        self.confirmed.emit()


def build_empty_card(d):
    card = Card()
    card.add(
        Label("還沒有紀錄", "title", INK),
        Label("島出現時點一下，或把游標移到螢幕上緣中間叫出來。", "body", INK2, elide=True),
        Label("第一次記錄之後，這裡就會開始累積。", "body", INK3, elide=True),
    )
    return card


# ---------------------------------------------------------------- 設定頁

class SettingsPage(QWidget):
    """設定。**只有四項，這是刻意的**——篩選標準見 settings.py 開頭。

    這一頁同時是「這個程式在你電腦上做了什麼」的交代處。對發布出去的工具，
    那比控制項更重要：使用者第一個問題是「它有沒有在傳我的資料」，
    而答案必須看得到，不是寫在 README 裡等人去翻。
    """

    changed = Signal(dict)          # 丟出整份新的 cfg
    reset_done = Signal()

    def __init__(self, cfg):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.cfg = dict(cfg)
        self.cards = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        # 間距一律自己宣告，不靠 layout 的預設值。兩者並存會疊加——
        # 上一版 setSpacing(GAP) 又手動 addSpacing(S4)，每個接縫實際是 40px 而不是 24。
        lay.setSpacing(0)

        # 一張卡分兩段，不是兩張卡。設定頁的高度必須跟紀錄那三頁一樣——
        # 換頁時會跳動的面板讀起來像兩個不同的視窗。內容區只有 558px，
        # 兩張卡光是內距與標題就吃掉 154px，那些空間該留給內容。
        self.card = self._settings_card()
        self.cards.append(self.card)
        lay.addWidget(self.card)

        # 破壞性動作放在卡片**外面**，用分隔線與一大段留白隔開。
        # 它跟上面那些「調整偏好」在語意上不是同一類東西，放進同一張卡
        # 就會被讀成清單裡的又一列，而滑鼠往下掃的路徑會經過它。
        lay.addSpacing(S5)
        lay.addWidget(Divider())
        lay.addSpacing(S3)
        self.danger = DangerAction("移除所有補水紀錄與連續天數，設定保留",
                                   "確定要清除所有紀錄嗎？")
        self.danger.confirmed.connect(self._on_reset)
        lay.addWidget(self.danger)

        lay.addStretch(1)
        lay.addWidget(Label(
            f"v{appsettings.VERSION}　·　體重僅儲存於本機　·　"
            f"每日目標依國民健康署一般建議推算，非醫療建議", "caption", INK3, elide=True))

    def sizeHint(self):
        """自動換行的文字要問 heightForWidth，不能問 sizeHint。

        QLabel 開了 wordWrap 之後，sizeHint 回報的是「還不知道寬度時的猜測」，
        實測比實際需要多 22px。多報的部分會變成視窗底部一塊莫名的留白，
        看起來像沒做完——這個檔案開頭那條「不捲動就一定要收到剛好」的規則，
        在有換行文字的頁面要靠 heightForWidth 才成立。
        """
        s = super().sizeHint()
        lay = self.layout()
        w = self.width()
        if w > 1 and lay and lay.hasHeightForWidth():
            return QSize(s.width(), lay.heightForWidth(w))
        return s

    # ------------------------------------------------------------ 卡片

    def _settings_card(self):
        """一張卡分兩段：可調的偏好，以及唯讀的說明。

        設定項的說明是標籤，不是文案：講清楚「這個值影響什麼」就停，
        不解釋機制、不講理由、不用第二人稱。理由屬於 README，不屬於介面。

        單位（公斤、分鐘）一律貼在控制項右邊，不寫進說明裡——
        單位是那個值的一部分，寫進說明就變成要讀完一句話才知道自己在設什麼。
        """
        card = Card()
        card.box.setSpacing(0)          # 列高已經釘死，列與列之間靠分隔線切開

        card.add(section_header("偏好設定"))
        card.add(GRID)

        self.weight = WeightField(self.cfg.get("weight_kg"))
        self.weight.editingFinished.connect(self._on_weight)
        card.add(setting_row("體重", row(self.weight,
                                        Label("公斤", "body", INK3), spacing=S2),
                             "用於推算每日目標"))

        # 每日目標是體重那一列的**結果**，不是另一個設定項——所以緊貼著它、
        # 中間不放分隔線。分隔線在這裡代表「這是另一件事」，用錯地方就會
        # 把因果關係切斷，讀起來像兩個無關的數字。
        self.target_lbl = Label("", "body", INK2)
        card.add(info_row("每日目標", "", self.target_lbl))
        card.add(Divider(inset=0))

        choices = appsettings.INTERVAL_CHOICES
        self.interval = Segmented([f"{m}" for m in choices])
        self.interval.setFixedWidth(280)
        cur = min(range(len(choices)),
                  key=lambda i: abs(choices[i] - self.cfg["interval_min"]))
        self.interval.set_index(cur, animate=False)
        self.interval.index = cur
        self.interval.changed.connect(self._on_interval)
        card.add(setting_row("提醒間隔",
                             row(self.interval, Label("分鐘", "body", INK3), spacing=S2),
                             "以在電腦前的時間計算，離開電腦不算"))
        card.add(Divider())
        self._refresh_target_label()

        screens = QApplication.screens()
        if len(screens) > 1:
            self._screens = screens
            self.screen_seg = Segmented([f"螢幕 {i + 1}" for i in range(len(screens))])
            self.screen_seg.setFixedWidth(min(280, 84 * len(screens)))
            cur = 0
            for i, s in enumerate(screens):
                if s.name() == self.cfg.get("screen_name"):
                    cur = i
            self.screen_seg.set_index(cur, animate=False)
            self.screen_seg.index = cur
            self.screen_seg.changed.connect(self._on_screen)
            self.screen_lbl = Label("", "caption", INK3, elide=True)
            g = screens[cur].geometry()
            card.add(setting_row("顯示螢幕", self.screen_seg,
                                 f"{g.width()}×{g.height()}"))
            self._refresh_screen_label()
        else:
            # 只有一個螢幕時不放控制項：單一選項的選擇器是雜訊，
            # 它讓人以為有得選，點下去才發現沒有。
            g = screens[0].geometry() if screens else None
            card.add(setting_row("顯示螢幕",
                                 Label(f"{g.width()}×{g.height()}" if g else "—",
                                       "body", INK2)))
        card.add(Divider())

        self.autostart = Toggle(appsettings.autostart_enabled())
        self.autostart.toggled.connect(self._on_autostart)
        card.add(setting_row("開機時啟動", self.autostart))

        # ---- 第二段：唯讀 ----
        card.add(S4)
        card.add(section_header("排程", self._schedule_note()))
        card.add(GRID)

        # 「換日」「深夜模式」是內部術語，使用者讀不出那是什麼意思，
        # 而且很容易誤解成「幾點睡」或「安靜時段」。改成講它實際造成什麼結果，
        # 並且**把真正的數字寫出來**——「23:00 後 65 分」不會有第二種解讀。
        rollover = self.cfg.get("day_rollover_hour", 4)
        late = self.cfg.get("late_night_start_hour", 23)
        late_min = appsettings.late_night_interval(self.cfg)
        card.add(info_row("今日次數歸零", f"每天 {rollover:02d}:00"))
        card.add(info_row("夜間放慢提醒", f"{late:02d}:00 起改為每 {late_min} 分"))

        open_lbl = TapLabel("開啟", C_ACCENT.name())
        open_lbl.clicked.connect(self._open_data_dir)
        card.add(info_row("資料位置", appsettings.DATA_DIR, open_lbl))
        return card

    def _schedule_note(self):
        """這兩個時間是怎麼來的。不能一律標「自動判定」——
        資料還不夠時用的是預設值，標成自動判定就是介面在說謊。
        """
        if not self.cfg.get("auto_schedule", True):
            return "手動指定"
        if appsettings.infer_schedule(appsettings.EVENTS_PATH):
            return "依你的活動紀錄自動判定"
        return "預設值，累積足夠紀錄後自動校準"

    # ------------------------------------------------------------ 事件

    def _emit(self):
        appsettings.save_config(self.cfg)
        self.changed.emit(dict(self.cfg))

    def _refresh_target_label(self):
        t = appsettings.effective_target(self.cfg)
        ml = t * self.cfg.get("ml_per_drink_estimate", 200)
        src = "由體重推算" if self.cfg.get("weight_kg") else "預設值"
        self.target_lbl.setText(f"{t} 次　·　約 {ml} cc　·　{src}")

    def _on_weight(self):
        kg = self.weight.value()
        if kg == self.cfg.get("weight_kg"):
            return
        self.cfg["weight_kg"] = kg
        # 填了體重就回到自動推導。使用者填體重的意思就是「幫我算」，
        # 若還沿用之前手動指定的次數，這個欄位看起來就是壞的。
        self.cfg["target_manual"] = False
        self.cfg["daily_target_drinks"] = appsettings.effective_target(self.cfg)
        self._refresh_target_label()
        self._emit()

    def _on_interval(self, i):
        self.cfg["interval_min"] = appsettings.INTERVAL_CHOICES[i]
        self._emit()

    def _on_screen(self, i):
        self.cfg["screen_name"] = self._screens[i].name()
        self._refresh_screen_label()
        self._emit()

    def _refresh_screen_label(self):
        s = self._screens[self.screen_seg.index]
        g = s.geometry()
        self.screen_lbl.setText(f"{g.width()}×{g.height()}")

    def _on_autostart(self, on):
        if not appsettings.set_autostart(on):
            # 寫不進去就把開關扳回去。一個顯示「開」但其實沒開的開關
            # 比沒有開關更糟——使用者會以為設好了，然後某天發現它沒起來。
            self.autostart.set_on(not on, emit=False)

    def _open_data_dir(self):
        try:
            os.makedirs(appsettings.DATA_DIR, exist_ok=True)
            os.startfile(appsettings.DATA_DIR)
        except (OSError, AttributeError):
            subprocess.Popen(["explorer", appsettings.DATA_DIR])

    def _on_reset(self):
        """確認已經在 DangerAction 裡就地問過了，這裡只負責執行。"""
        appsettings.reset_data()
        self.reset_done.emit()


# ---------------------------------------------------------------- 視窗

class StatsWindow(QWidget):
    def __init__(self, cfg, events_path, on_config=None):
        super().__init__()
        self.cfg = cfg
        self.events_path = events_path
        self.on_config = on_config
        self.mode = "stats"
        self._stats_stale = False     # 設定改過，回紀錄那邊時要重算
        self._drag = None
        self._closing = False
        self.cards = []

        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("喝水紀錄")
        self.resize(WIN_W + SHADOW * 2, WIN_H + SHADOW * 2)

        self.title_lbl = Label("喝水紀錄", "title", INK)
        # 副標在設定模式下兼任麵包屑。右上角那顆返回箭頭太小、也沒有標籤，
        # 使用者不一定認得它是「回上一層」——一條寫著去處的文字連結才是明確的路。
        self.sub_lbl = TapLabel("", INK3)
        self.sub_lbl.setFont(font("caption"))
        self.sub_lbl.clicked.connect(
            lambda: self._switch_mode("stats") if self.mode == "settings" else None)

        # 不捲動：內容分成幾頁，每一頁自己就放得下。
        # 捲動面板有兩個代價——使用者不知道下面還有什麼（成就永遠在看不到的地方），
        # 而且「這頁到底有多少東西」變成不可知，人就不會逛。
        self.seg = Segmented([p[0] for p in PAGES])
        self.stack = QStackedWidget()
        self.stack.setAttribute(Qt.WA_TranslucentBackground)
        self.seg.changed.connect(self._switch_page)

        stats_side = QWidget()
        stats_side.setAttribute(Qt.WA_TranslucentBackground)
        side_lay = QVBoxLayout(stats_side)
        side_lay.setContentsMargins(0, 0, 0, 0)
        side_lay.setSpacing(S4)
        side_lay.addWidget(self.seg)
        side_lay.addWidget(self.stack, 1)

        # 設定是另一個去處，不是第四個分頁——所以它跟整組分頁平行，
        # 放在外面這一層。這樣 refresh() 重建分頁時也不會把它一起拆掉。
        self.settings_page = SettingsPage(cfg)
        self.settings_page.changed.connect(self._on_config_changed)
        self.settings_page.reset_done.connect(self._on_reset_done)

        self.root = QStackedWidget()
        self.root.setAttribute(Qt.WA_TranslucentBackground)
        self.root.addWidget(stats_side)
        self.root.addWidget(self.settings_page)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SHADOW + WIN_PAD, SHADOW + WIN_PAD,
                                 SHADOW + WIN_PAD, SHADOW + WIN_PAD)
        outer.setSpacing(S4)
        outer.addWidget(col(self.title_lbl, self.sub_lbl, spacing=S1))
        outer.addWidget(self.root, 1)

        self.sp_win = Spring(0.0, *PRESET["enter"])
        self.setWindowOpacity(0.0)
        self._last = time.perf_counter()
        self.frame = QTimer(self)
        self.frame.setInterval(16)
        self.frame.timeout.connect(self._step)

        self.refresh()

    # ------------------------------------------------------------ 資料

    def refresh(self, animate=True):
        self.data = dashboard.compute(self.cfg, self.events_path)
        self.sub_lbl.setText(f"每日目標 {self.data['target']} 次")

        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()

        # 還沒有任何紀錄時不分頁——三個空頁面比一頁誠實的「還沒開始」糟得多
        pages = ([("開始", [build_empty_card, build_footer_card])]
                 if self.data["active_days"] == 0 else PAGES)
        self.seg.setVisible(len(pages) > 1)
        self.seg.labels = [p[0] for p in pages]
        self.seg.set_index(0, animate=False)
        self.seg.index = 0

        self.page_cards = []
        for _label, builders in pages:
            page = QWidget()
            page.setAttribute(Qt.WA_TranslucentBackground)
            lay = QVBoxLayout(page)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(GAP)
            cards = [b(self.data) for b in builders]
            for c in cards:
                lay.addWidget(c)
            lay.addStretch(1)          # 卡片往上靠，短的頁面不要被撐開
            self.page_cards.append(cards)
            self.stack.addWidget(page)

        if self.mode == "stats":
            self.cards = self.page_cards[0]
        self._fit_height()

        if animate:
            # 只重播卡片。refresh 也會在視窗已經開著的時候被呼叫（從系統匣再點一次），
            # 那時把整個視窗淡掉再淡回來，看起來像它關掉又開了一次。
            # 開窗本身的淡入由 open_window 呼叫 play_in() 負責。
            self.play_cards()
        else:
            for c in self.cards:
                c.sp.snap(1.0)
                c.set_reveal(1.0)
            self.sp_win.snap(1.0)
            self.setWindowOpacity(1.0)

    def _fit_height(self):
        """視窗高度收到「最高那一頁」剛好放得下。

        不捲動的面板一定要這樣做，否則短的頁面底下會留一大塊空白，
        看起來像壞掉或沒做完（實測沿用舊的 900 高，三頁各空了約 200px）。
        高度固定在最高頁，換頁時視窗不會跳動。

        **高度要問版面引擎，不要自己加總。** 手算標題、間距、分段控制項再加起來，
        等於把同一份版面算第二次——第一版就是這樣少算了 64px，三頁全部放不下。
        `QStackedWidget` 的 sizeHint 本來就是所有頁面的最大值，正好是我們要的。

        **設定頁不另外算高度，一律沿用紀錄那一側的。** 點齒輪是換內容，不是開另一個
        視窗；高度一跳，讀起來就像視窗關掉又開了一個新的。所以量的永遠是紀錄那一側，
        設定頁必須把內容收進同一個內容區——收不進去代表設定頁話太多，
        該刪的是字不是把視窗拉長。render_settings.py 會在放不下時擋下來。
        """
        for i in range(self.root.count()):
            w = self.root.widget(i)
            # 永遠讓紀錄那一側（index 0）決定高度，跟現在顯示哪一頁無關。
            w.setSizePolicy(QSizePolicy.Preferred,
                            QSizePolicy.Preferred if i == 0 else QSizePolicy.Ignored)
            # 巢狀的 layout 要自己 activate 一次。外層 activate() 不會遞迴下去，
            # 沒 activate 的容器其 sizeHint 是還沒算過的 (0, 0)——量出來的視窗
            # 就會是 277px 而不是 771px，而且不會有任何錯誤。
            if w.layout():
                w.layout().activate()
        self.root.adjustSize()
        lay = self.layout()
        lay.activate()
        need = lay.sizeHint().height()
        self.setFixedHeight(need)
        return need

    def showEvent(self, event):
        """視窗真的出現之後再量一次高度。

        建構時量不準：子元件還沒被 realize，QWidgetItem 對還沒顯示的 widget
        一律回報 0，量出來是 277px 而不是 771px——視窗會開成被切掉的一小條，
        而且沒有任何錯誤。渲染腳本剛好在 show() 之後又呼叫了一次 refresh()，
        把這個洞蓋住了，所以測試一直是綠的。
        高度只能在元件樹成形之後量，這是唯一保證成形的時機點。
        """
        super().showEvent(event)
        self._fit_height()

    # ------------------------------------------------------------ 設定

    def _switch_mode(self, mode, animate=True):
        """紀錄 <-> 設定。

        轉場只有淡入與依序進場，沒有橫向推移。真正的 push 要把兩頁同時擺在
        版面外再手動位移，那正是這個檔案開頭那條規則在防的事（版面交給 layout，
        不手算座標）。方向感改由「齒輪變成返回箭頭、分頁控制項收起、標題換掉」
        承載——那是結構訊號，比 18px 的位移更明確。
        """
        if mode == self.mode:
            return
        self.mode = mode
        if mode == "settings":
            self.title_lbl.setText("設定")
            self.sub_lbl.setText("‹ 喝水紀錄")          # 麵包屑，可點
            self.sub_lbl.setStyleSheet(f"color:{C_ACCENT.name()};background:transparent")
            self.sub_lbl.setCursor(Qt.PointingHandCursor)
            self.root.setCurrentIndex(1)
            self.cards = self.settings_page.cards
        else:
            self.root.setCurrentIndex(0)
            if self._stats_stale:
                # 目標次數變了，環、連續天數、成就的每個數字都要重算。
                # 重建放在「離開設定頁的那一刻」，不是改的當下——
                # 使用者還站在設定頁上時把它腳下的頁面抽掉，捲軸與焦點都會亂跳。
                self._stats_stale = False
                self.refresh(animate=False)
            self.title_lbl.setText("喝水紀錄")
            self.sub_lbl.setText(f"每日目標 {self.data['target']} 次")
            self.sub_lbl.setStyleSheet(f"color:{INK3};background:transparent")
            self.sub_lbl.setCursor(Qt.ArrowCursor)
            self.cards = self.page_cards[self.seg.index]
        self._fit_height()
        self.update()
        if animate:
            self.play_cards()

    def _on_config_changed(self, cfg):
        """設定頁改了東西。存檔已經在設定頁做掉，這裡負責往上通知島。"""
        self.cfg.update(cfg)
        if self.on_config:
            self.on_config(dict(self.cfg))
        # 目標次數會影響環、連續天數、成就的每一個數字，紀錄那邊要整份重算。
        # 但不能現在就重建——使用者還在設定頁上，重建會把他腳下的頁面抽掉。
        self._stats_stale = True

    def _on_reset_done(self):
        self._stats_stale = True
        self.settings_page.cfg = dict(self.cfg)

    def _switch_page(self, i):
        self.stack.setCurrentIndex(i)
        self.cards = self.page_cards[i]
        # 換頁重播進場：卡片依序滑入，讓人看見「這是一組新的東西」。
        # 用 play_cards 不是 play_in——視窗外框與標題沒有換，不該跟著閃。
        self.play_cards()

    # ------------------------------------------------------------ 動畫

    def play_in(self):
        """開窗：整個視窗淡入，然後卡片依序進場。"""
        self._closing = False
        self.sp_win.tune(*PRESET["enter"])
        self.sp_win.value = self.sp_win.velocity = 0.0
        self.sp_win.target = 1.0
        self.play_cards()

    def play_cards(self):
        """換頁：只有卡片重新進場，視窗本身不動。

        換頁不能重播 play_in()。那會把整個視窗的不透明度從 0 拉回 1，
        標題、外框、分頁控制項全部跟著閃一次——那不是換頁，看起來像視窗關掉重開。
        **只有真正換掉的東西該動**，沒換的東西動了就是在騙使用者說它變了。
        """
        for i, card in enumerate(self.cards):
            card.sp.value = card.sp.velocity = card.sp.target = 0.0
            card.set_reveal(0.0)
            QTimer.singleShot(40 + i * STAGGER_MS, lambda c=card: self._start(c))
        self._kick()

    def _start(self, card):
        card.sp.target = 1.0
        self._kick()

    def _kick(self):
        if not self.frame.isActive():
            self._last = time.perf_counter()
            self.frame.start()

    def _step(self):
        now = time.perf_counter()
        dt, self._last = now - self._last, now

        self.sp_win.step(dt)
        self.setWindowOpacity(clamp(self.sp_win.value, 0.0, 1.0))

        moving = not self.sp_win.settled
        for c in self.cards:
            if not c.sp.settled:
                c.sp.step(dt)
                c.set_reveal(clamp(c.sp.value, 0.0, 1.0))
                moving = True

        if self._closing and self.sp_win.value < 0.02:
            self.frame.stop()
            super().close()
            return
        if not moving:
            self.sp_win.snap()
            for c in self.cards:
                c.sp.snap()
                c.set_reveal(1.0)
            self.frame.stop()

    def close(self):
        """退場比進場快：進場要抓注意力，退場要讓開。"""
        if self._closing:
            return
        self._closing = True
        self.sp_win.tune(*PRESET["exit"])
        self.sp_win.target = 0.0
        self._kick()

    # 沒有 resizeEvent 了：分頁之後高度由內容決定，縱向縮放沒有意義，
    # QSizeGrip 一併移除。

    # ------------------------------------------------------------ 外框

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        body = QRectF(SHADOW, SHADOW, self.width() - SHADOW * 2, self.height() - SHADOW * 2)

        # 高斯衰減的疊層陰影（見 paintkit）。等透明度疊層只會得到硬邊與階梯感。
        draw_soft_shadow(p, body, SHADOW_ALPHAS,
                         offset_y=SHADOW_OFFSET_Y, corner=22)

        g = QLinearGradient(body.left(), body.top(), body.left(), body.bottom())
        g.setColorAt(0.0, C_BG_TOP)
        g.setColorAt(1.0, C_BG_BOTTOM)
        p.setPen(QPen(QColor(255, 255, 255, 28), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), 22, 22)

        hl = QLinearGradient(body.left(), body.top(), body.left(), body.top() + 80)
        hl.setColorAt(0.0, QColor(255, 255, 255, 30))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QBrush(hl), 1.0))
        p.drawRoundedRect(body.adjusted(1, 1, -1, -1), 21, 21)

        cx, cy = self.width() - SHADOW - WIN_PAD - 8, SHADOW + WIN_PAD + 14
        p.setPen(QPen(QColor(235, 235, 245, 214), 1.8, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPoint(cx - 7, cy - 7), QPoint(cx + 7, cy + 7))
        p.drawLine(QPoint(cx - 7, cy + 7), QPoint(cx + 7, cy - 7))

        # 齒輪（在設定頁時換成返回箭頭）。放在 × 左邊：關閉永遠在最外側，
        # 那是 Windows 的位置慣例，把它往內擠會讓人關錯。
        gx = cx - GEAR_GAP
        p.setPen(QPen(QColor(235, 235, 245, 214), 1.8, Qt.SolidLine, Qt.RoundCap,
                      Qt.RoundJoin))
        if self.mode == "settings":
            p.drawLine(QPoint(gx + 7, cy), QPoint(gx - 6, cy))
            p.drawLine(QPoint(gx - 6, cy), QPoint(gx - 1, cy - 5))
            p.drawLine(QPoint(gx - 6, cy), QPoint(gx - 1, cy + 5))
        else:
            self._draw_gear(p, gx, cy)

    @staticmethod
    def _draw_gear(p, cx, cy):
        """齒輪：外圈八個齒 + 中間一個孔。

        八個齒是「看得出是齒輪」的最少數量——六個看起來像星星，
        十個在 28px 見方會糊成一個圓。
        """
        r_out, r_in, r_hole = 8.4, 5.8, 2.6
        path = QPainterPath()
        teeth = 8
        for i in range(teeth * 2):
            ang = math.pi * i / teeth - math.pi / 2
            r = r_out if i % 2 == 0 else r_in
            x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        path.closeSubpath()
        p.drawPath(path)
        p.drawEllipse(QRectF(cx - r_hole, cy - r_hole, r_hole * 2, r_hole * 2))

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        pos = event.position()
        head_bottom = SHADOW + WIN_PAD + self.title_lbl.height() + self.sub_lbl.height() + S1
        if SHADOW <= pos.y() < head_bottom and pos.x() >= SHADOW:
            right = self.width() - SHADOW - WIN_PAD
            if pos.x() > right - 24:
                self.close()
                return
            # 齒輪的可點範圍比畫出來的圖大一圈：16px 的圖示要 40px 的點擊區，
            # 否則得瞄準才點得到。這是觸控與滑鼠都適用的最小尺寸。
            if right - 24 - GEAR_GAP <= pos.x() <= right - GEAR_GAP + 16:
                self._switch_mode("stats" if self.mode == "settings" else "settings")
                return
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, event):
        self._drag = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()


def open_window(cfg, events_path, existing=None, on_config=None, on_settings=False):
    typeface.ensure_loaded()      # 只會做一次；讓渲染腳本單獨開視窗時也拿得到字體
    win = existing
    if win is None or not win.isVisible():
        win = StatsWindow(cfg, events_path, on_config=on_config)
        if on_settings:
            win._switch_mode("settings", animate=False)
        screen = QApplication.primaryScreen().availableGeometry()
        win.move(screen.center().x() - win.width() // 2,
                 max(screen.top() + 10, screen.center().y() - win.height() // 2))
        win.show()
        win.play_in()
    else:
        win._switch_mode("settings" if on_settings else "stats", animate=False)
        if win.mode == "stats":
            win.refresh()
        win.show()
    win.raise_()
    win.activateWindow()
    return win

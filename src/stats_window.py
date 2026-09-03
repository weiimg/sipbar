# -*- coding: utf-8 -*-
"""喝水紀錄視窗。

## 為什麼用版面引擎而不是自己算座標

前幾版把每個元素的位置寫成 paintEvent 裡的魔術數字（`top + 88`、`cy - 12`…），
結果是同一類 bug 一直重複出現：卡片高度用猜的所以內容被切掉、對齊靠巧合所以
出現三條左緣、字級一改整張版面就跑掉。

改成：結構交給 Qt 的 layout，文字交給 QLabel，只有真正的圖形（環、火焰、護盾、
熱力圖、進度條）才自繪。於是——

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

import PySide6
from PySide6.QtCore import (
    QPoint, QPointF, QRectF, Qt, QTimer, Signal, qVersion,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QIntValidator, QLinearGradient,
    QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QLineEdit, QScrollArea, QSizePolicy, QStackedWidget,
    QVBoxLayout, QWidget,
)

import dashboard
import pixelface                             # 島上那顆像素杯，紀錄頁共用同一個容器
import settings as appsettings               # 設定的讀寫與推導
import updates                                # 有沒有新版（齒輪上那顆點）
import sound                                  # 音效開關的當場試聽
import theme                                  # 深色／淺色調色盤
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
# 會整團糊在一起，加粗反而更糟。中文小字的瓶頸是像素數，不是字重或對比。
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

# 接近性原則：標題與它的說明要貼緊，列與列之間要拉開。
# 兩者是同一組資訊，靠得近才讀成一組；真正需要距離的是「這一項」與「下一項」之間。
# 這兩個值一起看才有意義——只看單一個數字沒辦法判斷夠不夠。
LABEL_GAP = 2                             # 標題 ↔ 它自己的說明（同一組，貼緊）
ROW_GAP = 8                               # 列 ↔ 列（不同項目，拉開；分隔線落在中間）

# 設定裡控制項的高度。比導覽用的分段控制項（Segmented.H = 40）矮一級：
# 控制項是用來操作那一列的，不該比它標示的內容更搶眼。
CTRL_H = 34
CTRL_W = 240                              # 分段控制項的寬度。
                                          # 280 在 706px 的內容區裡佔 40%，太重
# 控制項裡的字級也要跟著縮。只把框改小、字留原尺寸，字會把框撐得很滿，
# 看起來仍然是個重的元件——縮小控制項不是只縮外框。
CTRL_TYPE = "caption"
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

# 顏色全部來自 theme.py 的調色盤，這裡只是「目前主題」的快照。
# 換主題要呼叫 apply_theme() 重新取值，而且視窗要重建——
# 文字顏色是在建立 QLabel 的當下寫進 stylesheet 的，改了模組變數不會回頭修改已存在的元件。
PAL = theme.active()
INK = INK2 = INK3 = C_DANGER = ""
C_ACCENT = C_GREEN = C_FLAME = C_FLAME2 = None
C_SLOT = C_CARD_TOP = C_CARD_BOTTOM = C_BG_TOP = C_BG_BOTTOM = None


def _alpha(color, a):
    """同一個顏色換一個透明度。語意色在兩套主題不同值，不能寫死 RGB。"""
    c = QColor(color)
    c.setAlpha(a)
    return c


def apply_theme(name=None):
    """套用主題並刷新這個模組的顏色快照。回傳生效的調色盤。"""
    global PAL, INK, INK2, INK3, C_DANGER, C_ACCENT, C_GREEN, C_FLAME, C_FLAME2
    global C_SLOT, C_CARD_TOP, C_CARD_BOTTOM, C_BG_TOP, C_BG_BOTTOM
    global C_DIVIDER, SHADOW_ALPHAS
    PAL = theme.apply(name) if name is not None else theme.active()
    INK, INK2, INK3 = PAL.ink, PAL.ink2, PAL.ink3
    C_DANGER = f"rgba({PAL.danger.red()},{PAL.danger.green()},{PAL.danger.blue()},1)"
    C_ACCENT, C_GREEN = PAL.accent, PAL.green
    C_FLAME, C_FLAME2 = PAL.flame, PAL.flame2
    C_SLOT = PAL.veil(24)
    C_DIVIDER = PAL.veil(20)
    C_CARD_TOP, C_CARD_BOTTOM = PAL.card_top, PAL.card_bottom
    # 視窗底色留一點透明度，讓底下的桌面透出來一點點（原本就是 252/255）
    C_BG_TOP, C_BG_BOTTOM = _alpha(PAL.bg_top, 252), _alpha(PAL.bg_bottom, 252)
    # 陰影濃度跟著主題走：同一個 alpha 的黑影壓在淺色底上會重得多
    SHADOW_ALPHAS = shadow_alphas(SHADOW - 2, PAL.shadow_peak, SHADOW_SIGMA)
    return PAL

apply_theme()          # 模組載入時先套一次，之後由設定或系統決定

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


def para(text, role="caption", color=None):
    """會換行的整段說明。

    顏色預設用第二層而不是第三層：第三層是給「掃過去就好」的註記用的，
    成段的說明是要讀完的。淺色主題上第三層只有 3.9:1，一整段那樣讀很吃力。

    Label 的省略號是給「一行放不下就切掉」的欄位用的——那適合數值旁邊的短註解，
    不適合成段的說明：一段話被切成「…程式看你的活動紀…」等於完全沒說。
    需要讀完的文字就要換行，能捨棄的才用省略號。
    """
    lbl = QLabel(text)
    lbl.setFont(font(role))
    lbl.setStyleSheet(f"color:{color or INK2};background:transparent")
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

class Tip(QWidget):
    """自繪的提示泡泡。

    ## 為什麼不用 QToolTip

    跟先前換掉 QMenu、QMessageBox 完全同一個理由：系統的提示是方角、系統字、
    自己一套配色，在一片自繪的介面旁邊就是一塊補丁。而且它有兩個改不掉的行為：

    - **要等。** 預設延遲將近一秒，短到讓人以為沒有提示、長到等不下去。
      這裡的提示是「滑過去看一眼」的東西，等待本身就抵銷了它的用處。
    - 視窗不是作用中的時候整個不出現（`WA_AlwaysShowToolTips` 治得了這一項，
      但治不了外觀與延遲）。

    自己畫就三件事都解決了：立刻出現、同一套圓角陰影與字體、跟視窗狀態無關。

    ## 只有一顆

    模組層級的單例。同時冒出兩個提示是不可能發生的事，做成多實例只會多出
    「誰負責關掉誰」的問題——熱圖那種逐格移動的提示尤其容易漏關。

    ## 滑鼠穿透要用 WindowTransparentForInput，不是 WA_TransparentForMouseEvents

    這兩個名字很像，作用的層級不同，而**只設後者會壞得很難查**：

    `WA_TransparentForMouseEvents` 是 Qt 內部在分派事件時跳過這個元件，對子元件
    有效。但這顆泡泡是獨立的頂層視窗，作業系統仍然把它當成一扇會接滑鼠的窗——
    於是游標一飄到它上面，來源就收到 Leave，而**接下來整個視窗裡再也沒有任何
    元件收得到 Enter**。實測就是這個症狀：第一個提示出得來，之後全部啞掉，
    連原本正常的那個再滑一次也不出現。

    `Qt.WindowTransparentForInput` 才是頂層那一層的開關，它讓這扇窗在作業系統
    的命中測試裡直接不存在。兩個都設著：一個管 Qt 內部，一個管視窗系統。
    """

    PAD_H, PAD_V = 12, 8
    RADIUS = 10
    SHADOW = 16
    GAP = 8                      # 泡泡與來源之間的距離

    _one = None

    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint |
                         Qt.NoDropShadowWindowHint |
                         Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        # 不搶焦點。搶了的話紀錄視窗會失去作用中狀態，標題列跟著變灰。
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._text = ""
        self._alphas = shadow_alphas(Tip.SHADOW - 2, PAL.shadow_peak * 1.1, 6.0)

    # -------------------------------------------------------- 對外的三個入口

    @classmethod
    def _instance(cls):
        # 換主題會重建整個視窗，但這一顆掛在模組上活得比視窗久，
        # 所以每次拿的時候順手把配色重讀一次。
        if cls._one is None:
            cls._one = Tip()
        cls._one._alphas = shadow_alphas(Tip.SHADOW - 2, PAL.shadow_peak * 1.1, 6.0)
        return cls._one

    @classmethod
    def show_for(cls, widget, text):
        """貼在某個元件的正上方。給固定位置的提示用（護盾、杯子）。

        對齊來源的中心而不是游標：來源不會動，提示就不該跟著手抖。
        """
        if not text:
            return
        tip = cls._instance()
        tip._lay(text)
        top = widget.mapToGlobal(QPoint(widget.width() // 2, 0))
        tip._place(top.x() - tip.width() // 2,
                   top.y() - tip.height() + Tip.SHADOW - Tip.GAP,
                   fallback_y=top.y() + widget.height() - Tip.SHADOW + Tip.GAP)

    @classmethod
    def show_at(cls, global_pos, text):
        """跟著游標。給熱圖、週曆那種一個元件裡有很多格的情況。"""
        if not text:
            return
        tip = cls._instance()
        tip._lay(text)
        tip._place(global_pos.x() - tip.width() // 2,
                   global_pos.y() - tip.height() + Tip.SHADOW - Tip.GAP,
                   fallback_y=global_pos.y() - Tip.SHADOW + Tip.GAP * 3)

    @classmethod
    def hide_tip(cls):
        """收起來。已經被 Qt 回收掉也不能炸。

        關閉程式時的拆除順序會走到這裡：Qt 先把這顆泡泡的 C++ 物件回收，
        然後才輪到視窗的 hideEvent——而那裡會再叫一次 hide_tip()。
        Python 這邊的參考還在，底下的東西已經沒了，`hide()` 直接拋 RuntimeError。

        症狀是關程式時在 atexit 吐一段 traceback。使用者看到「程式關掉時報錯」，
        而實際上什麼事都沒有——那種訊息只會讓人以為壞了。
        """
        if cls._one is None:
            return
        try:
            cls._one.hide()
        except RuntimeError:
            cls._one = None

    # -------------------------------------------------------- 內部

    def _lay(self, text):
        self._text = text
        fm = QFontMetrics(font("caption"))
        lines = text.split("\n")
        w = max(fm.horizontalAdvance(x) for x in lines) + Tip.PAD_H * 2
        h = fm.height() * len(lines) + Tip.PAD_V * 2
        self.resize(int(w) + Tip.SHADOW * 2, int(h) + Tip.SHADOW * 2)

    def _place(self, x, y, fallback_y):
        """擺上去，並確保整個泡泡留在螢幕內。

        上方放不下就翻到下方——這是原生提示自動做、自繪就得自己做的事，
        跟 `menu.TrayMenu.popup_at()` 同一個道理。
        """
        area = (QApplication.screenAt(QPoint(int(x), int(y)))
                or QApplication.primaryScreen()).availableGeometry()
        if y + Tip.SHADOW < area.top():
            y = fallback_y
        x = max(area.left() - Tip.SHADOW,
                min(x, area.right() - self.width() + Tip.SHADOW))
        self.move(int(x), int(y))
        self.show()
        self.raise_()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        body = QRectF(Tip.SHADOW, Tip.SHADOW,
                      self.width() - Tip.SHADOW * 2,
                      self.height() - Tip.SHADOW * 2)
        draw_soft_shadow(p, body, self._alphas, offset_y=4, corner=Tip.RADIUS)

        g = QLinearGradient(body.left(), body.top(), body.left(), body.bottom())
        g.setColorAt(0.0, QColor(PAL.bg_top))
        g.setColorAt(1.0, QColor(PAL.bg_bottom))
        p.setPen(QPen(PAL.veil(30), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5),
                          Tip.RADIUS, Tip.RADIUS)

        p.setFont(font("caption"))
        p.setPen(PAL.ink_a(225))
        fm = QFontMetrics(font("caption"))
        y = body.top() + Tip.PAD_V + fm.ascent()
        for line in self._text.split("\n"):
            p.drawText(int(body.left() + Tip.PAD_H), int(y), line)
            y += fm.height()


class Graphic(QWidget):
    """自繪的葉節點。reveal 由卡片統一餵進來驅動內部的值動畫。

    `set_tip()` 掛上去的提示走自繪的 `Tip`，不走 `setToolTip()`——
    立刻出現、外觀一致，理由見 Tip 的 docstring。
    """

    def __init__(self, w=None, h=None):
        super().__init__()
        self.reveal = 1.0
        self._tip = ""
        self.setAttribute(Qt.WA_TranslucentBackground)
        if w is not None:
            self.setFixedWidth(w)
        if h is not None:
            self.setFixedHeight(h)

    def set_reveal(self, t):
        self.reveal = t
        self.update()

    def set_tip(self, text):
        self._tip = text or ""

    def enterEvent(self, event):
        if self._tip:
            Tip.show_for(self, self._tip)

    def leaveEvent(self, event):
        if self._tip:
            Tip.hide_tip()

    def hideEvent(self, event):
        # 換頁時提示要跟著走。它是獨立的頂層視窗，來源被藏起來不會自動把它
        # 帶走——留在螢幕上就是一塊擦不掉的字。
        #
        # **這一條擋不到「整個視窗關掉」。** Qt 只對「自己被隱藏」的那個元件送
        # Hide，父層被隱藏時子元件收到的是 HideToParent，不會走進這裡。
        # 所以視窗那一層另外接一次，見 StatsWindow.hideEvent()。
        Tip.hide_tip()


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

        p.setPen(QPen(PAL.veil(28), 11))
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
        p.setPen(PAL.ink_a(255))
        # 數字沒有下伸部，用 cap height 對齊才是光學置中
        p.drawText(int(cx - fm.horizontalAdvance(num) / 2),
                   int(round(cy + fm.capHeight() / 2)), num)


class CupGauge(Graphic):
    """今日進度：像素杯的水位 + 次數 + 換算的 cc。取代原本的環。

    這是量表，不是插畫。卡片上已經有一個大圖示（火焰，連續天數的徽記），
    再放第二個同等份量的圖形，兩個會互相競爭、看不出誰是主角。
    所以杯子收在原本環的footprint 裡（132 寬），杯身只佔上半，
    底下兩行文字——讀起來是一個儀表，不是另一張插畫。

    用島上那顆杯子而不是另畫一個容器，是為了讓兩個畫面說同一種話：
    島上那杯水降下去代表該喝了，這裡那杯水升上來代表今天喝了多少。
    同一個容器，兩個方向。

    cc 是換算不是紀錄。這個工具刻意數「次」——被提醒時你只會喝幾口，
    用 cc 當計數單位會逼人虛報或不敢按（見 README）。所以它小一級、灰一階。
    """

    W = 132
    CELL = 5

    def __init__(self, done, target, ml_each):
        cw, ch = pixelface.cup_size(self.CELL)
        super().__init__(self.W, ch + 46)
        self.done, self.target, self.ml = done, target, ml_each
        self.cup_h = ch

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        t = clamp(ease(self.reveal), 0.0, 1.0)
        p.setOpacity(t)

        ratio = clamp(self.done / max(1, self.target), 0.0, 1.0) * t
        pixelface.draw_cup(p, self.W // 2, self.cup_h // 2 + 2, ratio, "NORMAL",
                           pixelface.GLASS, pixelface.WATER, pixelface.INK,
                           cell=self.CELL)

        f = font("headline")
        fm = QFontMetrics(f)
        p.setFont(f)
        p.setPen(PAL.ink_a(255))
        main = f"{self.done} / {self.target} 次"
        p.drawText(int((self.W - fm.horizontalAdvance(main)) / 2),
                   self.cup_h + 22, main)

        f2 = font("caption")
        fm2 = QFontMetrics(f2)
        p.setFont(f2)
        p.setPen(PAL.ink_a(140))
        sub = f"約 {self.done * self.ml} / {self.target * self.ml} cc"
        p.drawText(int((self.W - fm2.horizontalAdvance(sub)) / 2),
                   self.cup_h + 42, sub)


class Flame(Graphic):
    """連續天數的火焰。

    進場時彈簧驅動竄起動畫，點亮的火焰竄完後持續搖曳。
    動畫由自己的 Spring + QTimer 驅動，不走卡片的共用計時器。
    """

    def __init__(self, lit, w=76, h=112):
        super().__init__(w, h)
        self.lit = lit
        self._armed = False
        self._burst_sp = None
        self._burst_timer = None
        self._burst_t = 1.0
        self._idle = False
        self._t0 = 0.0

    def set_reveal(self, t):
        self.reveal = t
        if t < 0.01:
            self._armed = True
            self._idle = False
            self._burst_t = 0.0
            if self._burst_timer and self._burst_timer.isActive():
                self._burst_timer.stop()
            self._burst_sp = None
        elif self._armed and t >= 0.7:
            self._armed = False
            self._ignite()
        self.update()

    def _ignite(self):
        self._burst_sp = Spring(0.0, 0.32, 0.55)
        self._burst_sp.target = 1.0
        self._burst_last = time.perf_counter()
        if self._burst_timer is None:
            self._burst_timer = QTimer(self)
            self._burst_timer.setInterval(16)
            self._burst_timer.timeout.connect(self._burst_tick)
        else:
            self._burst_timer.setInterval(16)
        self._burst_timer.start()

    _IDLE_DUR = 1.5

    def _burst_tick(self):
        now = time.perf_counter()
        if self._idle:
            t = now - self._t0
            if t >= self._IDLE_DUR:
                self._idle = False
                self._burst_t = 1.0
                self._burst_timer.stop()
                self.update()
                return
            fade = 1.0 - t / self._IDLE_DUR
            self._burst_t = 1.0 + fade * (0.04 * math.sin(t * 2.8)
                                           + 0.025 * math.sin(t * 4.3))
            self.update()
            return
        dt = now - self._burst_last
        self._burst_last = now
        self._burst_sp.step(dt)
        self._burst_t = self._burst_sp.value
        if self._burst_sp.settled:
            self._burst_t = 1.0
            if self.lit:
                self._idle = True
                self._t0 = now
                self._burst_timer.setInterval(33)
            else:
                self._burst_timer.stop()
        self.update()

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
        if self._burst_sp is not None:
            h = (self.height() - 6) * max(0.0, self._burst_t)
        elif self._armed:
            h = 0
        else:
            h = (self.height() - 6) * lerp(0.74, 1.0, ease(self.reveal))
        if h < 1:
            return
        cx, bottom = self.width() / 2, self.height() - 3
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(C_FLAME if self.lit else C_SLOT))
        p.drawPath(self._path(cx, bottom, h))
        inner_dy = 0
        if self._idle:
            t = time.perf_counter() - self._t0
            fade = max(0.0, 1.0 - t / self._IDLE_DUR)
            inner_dy = fade * 1.5 * math.sin(t * 3.5)
        p.setBrush(QBrush(C_FLAME2 if self.lit else PAL.veil(16)))
        p.drawPath(self._path(cx, bottom - h * 0.06 + inner_dy, h * 0.56))


class Shields(Graphic):
    """護盾圖示本身就是那一列的全部。

    這一列的右邊走過三個版本：先是常駐的「8/13 已消耗」（使用者問「這是什麼」
    ——它緊挨著計數用的圖示，日期被讀成分數），改成「9月1日補滿」，
    再收進一顆 ⓘ。最後拿掉了。

    收斂到這裡的理由是每一版都在回答同一個問題的更小版本：**護盾會自己運作，
    不知道細節不影響任何事。** 那顆 ⓘ 雖然只有 16px，仍然是在一列不需要說明的
    東西旁邊放一個「這裡有說明」的記號，而圖示自己就已經是可以滑過去的東西了。

    所以說明掛在圖示上，那一列乾乾淨淨。
    """

    STEP, R = 38, 14

    def __init__(self, total, left, tip=""):
        super().__init__(total * Shields.STEP, Shields.R * 2 + S2)
        self.total = total
        self.left = left
        self.set_tip(tip)

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
            p.setPen(QPen(C_ACCENT if on else PAL.veil(46), 2.2))
            p.setBrush(QBrush(_alpha(C_ACCENT, 72) if on else Qt.transparent))
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

            # 今天用「星期標成藍色」來標，不再在圓外面加一圈。
            #
            # 先前那一圈跟裡面的進度是同一個藍、只差粗細，兩個同心圓疊在一起
            # 讀起來像畫歪了——使用者的原話是「外圍藍色線條的設計有點奇怪」。
            # 標籤本來就在那裡、本來就會為今天換顏色，把它換成強調色就夠了，
            # 不必為此多佔任何空間。
            p.setFont(font("body"))
            p.setPen(C_ACCENT if day["today"] else PAL.ink_a(168))
            lw = fm_l.horizontalAdvance(day["label"])
            p.drawText(int(cx - lw / 2), int(fm_l.ascent()) + 2, day["label"])

            p.setPen(Qt.NoPen)
            box = QRectF(cx - r, cy - r, r * 2, r * 2)
            if day["future"]:
                p.setBrush(QBrush(PAL.veil(14)))
                p.drawEllipse(box)
                note = "還沒到"
            elif day["hit"]:
                p.setBrush(QBrush(C_GREEN))
                p.drawEllipse(box)
                # 打勾畫在飽和的綠色圓點上，兩套主題都該是深色——
                # 它的底不是頁面底色，是那顆圓點，所以不跟著主題翻。
                p.setPen(QPen(QColor(16, 22, 18), 3.6, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPoint(int(cx - r * 0.34), int(cy + r * 0.02)),
                           QPoint(int(cx - r * 0.08), int(cy + r * 0.28)))
                p.drawLine(QPoint(int(cx - r * 0.08), int(cy + r * 0.28)),
                           QPoint(int(cx + r * 0.36), int(cy - r * 0.26)))
                note = f"{day['drinks']} / {self.target} 次，達標"
            elif day["used"]:
                # 進度畫成水位，不畫環。
                #
                # 這是一個喝水的工具，圓圈裡裝著水是它唯一不用學就懂的圖形，
                # 而且跟島上那顆像素杯講同一件事——整套視覺語言收斂到一個比喻。
                #
                # 環還有一個具體的問題：粗弧配圓頭端點看起來像載入中的轉圈，
                # 那是「等待」的語彙，不是「你喝了 2 次」。
                pct = (day["drinks"] / self.target) * local if self.target else 0
                p.setBrush(QBrush(PAL.veil(16)))
                p.drawEllipse(box)
                if pct > 0:
                    # 裁進圓裡再畫矩形，水面就是一條平的線——圓弧的水面要另外
                    # 算貝茲曲線，而在這個尺寸下看不出差別。
                    clip = QPainterPath()
                    clip.addEllipse(box)
                    p.save()
                    p.setClipPath(clip)
                    p.setBrush(QBrush(C_ACCENT))
                    p.drawRect(QRectF(cx - r, cy + r - 2 * r * pct, r * 2, 2 * r * pct))
                    p.restore()
                n = str(day["drinks"])
                p.setFont(font("headline"))
                p.setPen(PAL.ink_a(255))
                p.drawText(int(cx - fm_n.horizontalAdvance(n) / 2),
                           int(cy + fm_n.capHeight() / 2), n)
                note = f"{day['drinks']} / {self.target} 次"
            else:
                p.setBrush(QBrush(C_SLOT))
                p.drawEllipse(box)
                note = "沒開電腦，不計入連續"

            self._hit.append((QRectF(cx - rad - 8, cy - rad - 8, (rad + 8) * 2, (rad + 8) * 2),
                              f"{day['key']}　{note}"))

    def mouseMoveEvent(self, event):
        pos = event.position()
        for rect, text in self._hit:
            if rect.contains(pos):
                Tip.show_at(event.globalPosition().toPoint(), text)
                return
        Tip.hide_tip()


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
        p.setPen(PAL.ink_a(168))
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
                # 每一格用「那天的目標」上色，不是現在的目標。
                # 這裡原本吃 self.data["target"]，於是調一次體重或單次水量，
                # 整片熱圖的顏色就跟著重畫一次——8/10 當天 7/7 是滿的，
                # 目標改成 9 之後那一格會從全綠掉成淺綠。跟達標判定是同一個
                # 回溯問題（見 dashboard.day_target），當時漏了這裡。
                tgt = (dashboard.day_target(info, key, self.data["today_key"], target)
                       if info else target)
                c = cell * lerp(0.55, 1.0, local)
                off = (cell - c) / 2
                x, y = self.LABEL_W + w * step, wd * step
                p.setBrush(QBrush(self._color(info, tgt)))
                p.drawRoundedRect(QRectF(x + off, y + off, c, c), 5, 5)

                n = info["drinks"] if info else 0
                if key in self.data["streak"]["saved_days"]:
                    note = f"{n} / {tgt} 次，護盾已消耗"
                elif info and (info["drinks"] or info["reminds"]):
                    note = f"{n} / {tgt} 次"
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
            return _alpha(C_GREEN, 175)
        if ratio >= 0.33:
            return _alpha(C_ACCENT, 160)
        if ratio > 0:
            return _alpha(C_ACCENT, 96)
        return PAL.veil(52)

    def mouseMoveEvent(self, event):
        pos = event.position()
        for rect, text in self._hit:
            if rect.contains(pos):
                Tip.show_at(event.globalPosition().toPoint(), text)
                return
        Tip.hide_tip()


class Bar(Graphic):
    def __init__(self, pct, w=96):
        super().__init__(w, 8)
        self.pct = pct

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(PAL.veil(26)))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 4, 4)
        v = self.pct * ease(self.reveal)
        if v > 0:
            p.setBrush(QBrush(C_ACCENT))
            p.drawRoundedRect(QRectF(0, 0, max(8, self.width() * v), self.height()), 4, 4)


_BADGE_ICONS = [
    # 0: 水啦 — smiling water drop
    (["........",
      "...BB...",
      "..BBBB..",
      ".BBBBBB.",
      ".MWMMWM.",
      ".DDWWDD.",
      "..DDDD..",
      "........"], 3),
    # 1: 今天很水哦 — smiling cup
    (["KBBBBBBK",
      "KBBBBBBK",
      "KBWBBWBK",
      "KBBBBBBK",
      "KMWMMWMK",
      "KDDWWDDK",
      "KDDDDDDK",
      ".KKKKKK."], 3),
    # 2: One, two, 水！ — cup
    (["........",
      ".DBBBBD.",
      ".DWBBWD.",
      ".DBWWBD.",
      ".DBBBBD.",
      "..DBBD..",
      "...BD...",
      "..DDDD.."], 3),
    # 3: 需要你 — crying cup
    (["KBBBBBBK",
      "KBBBBBBK",
      "KBWBBWBK",
      "KBBBBBBK",
      "KMWWWWMK",
      "KWDDDDWK",
      "KDDDDDDK",
      ".KKKKKK."], 3),
    # 4: 我是一隻魚 — fish
    (["........",
      "..DDL...",
      ".BBBBL.D",
      "BWBBWDLD",
      "LBWWDBDD",
      ".LLLLD.D",
      "...LD...",
      "........"], 3),
    # 5: 一氧化二氫成癮者 — H₂O
    (["LD....LD",
      "DD....DD",
      "..L..L..",
      "...BM...",
      "..BBMD..",
      ".MWMMWD.",
      "..DWWD..",
      "...DD..."], 3),
]


def _badge_shades(done):
    if done:
        b = C_ACCENT
        return {
            'B': b,
            'L': b.lighter(108),
            'M': b.darker(115),
            'D': b.darker(135),
            'K': b.darker(165),
            'W': QColor(255, 255, 255),
        }
    g = QColor(140, 140, 140)
    return {
        'B': _alpha(g, 77),
        'L': _alpha(g, 65),
        'M': _alpha(g, 90),
        'D': _alpha(g, 110),
        'K': _alpha(g, 128),
        'W': _alpha(QColor(200, 200, 200), 50),
    }


class Badge(Graphic):
    def __init__(self, done, remain, icon=0, size=44):
        super().__init__(size, size)
        self.done = done
        self.remain = remain
        self.icon = icon

    def paintEvent(self, event):
        e = ease(self.reveal)
        if e < 0.01:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setOpacity(e)
        grid, cell = _BADGE_ICONS[self.icon]
        gw, gh = len(grid[0]), len(grid)
        ox = (self.width() - gw * cell) // 2
        oy = (self.height() - gh * cell) // 2
        colors = _badge_shades(self.done)
        for gy, row_str in enumerate(grid):
            for gx, ch in enumerate(row_str):
                if ch != '.' and ch in colors:
                    p.fillRect(ox + gx * cell, oy + gy * cell,
                               cell, cell, colors[ch])


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
        value = clamp(ease(t), 0.0, 1.0)
        self._fx.setOpacity(value)
        # 完全不透明時把效果關掉：淡入結束之後它本來就不做事（opacity 1.0），
        # 而掛著 QGraphicsEffect 的 widget 一律要先畫進離屏圖再合成，白付成本。
        #
        # 這不是「設定頁捲動時版面錯位」那個 bug 的修正。我一度以為是，
        # 理由是效果的離屏圖在捲動時不會失效；但把效果強制開回來當對照組跑，
        # 殘影的量跟關掉時一樣（實測 34278 vs 34206 個像素）。假設被推翻了，
        # 這行留著只是因為它本身划算。那個 bug 到目前為止還沒找到原因：
        # 版面在每一條路徑上量出來都是對的（371/274/338、間距 17px），
        # 畫面上卻差了 200px，所以問題在繪製，不在幾何。
        self._fx.setEnabled(value < 0.999)
        for w in self.findChildren(QWidget):
            if w is not self and hasattr(w, "set_reveal"):
                w.set_reveal(t)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0.0, C_CARD_TOP)
        g.setColorAt(1.0, C_CARD_BOTTOM)
        p.setPen(QPen(PAL.veil(20), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 20, 20)
        hl = QLinearGradient(0, 0, 0, self.height() * 0.5)
        hl.setColorAt(0.0, PAL.veil(26))
        hl.setColorAt(1.0, PAL.veil(0))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QBrush(hl), 1.0))
        p.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 19, 19)


def build_streak_card(d):
    t, today, streak = d["target"], d["today"]["drinks"], d["streak"]["streak"]
    s = d["streak"]
    left = t - today
    # 語域：進行中講「再幾次會發生什麼」——把結果說出來比催促有效，而且每天讀都還行。
    # 達標當下才用驚嘆號：那是一次性的獎勵時刻，天天用會很快失效、甚至變吵。
    if today >= t:
        status = f"達標！連續第 {streak} 天" if streak else "今天達標！"
    elif streak > 0:
        status = f"再 {left} 次，連續來到第 {streak + 1} 天"
    elif today > 0:
        status = f"還差 {left} 次達標"
    else:
        status = "今天還沒開始"

    num = CountLabel(streak, "display", INK if streak else INK3)
    gauge = CupGauge(today, t, d["ml"])
    gauge.set_tip(f"今天 {today} / {t} 次")

    card = Card()
    card.add(
        row(Flame(streak > 0),
            (col(row(num, Label("天", "section", INK2), "stretch", spacing=S2),
                 Label("連續達標", "caption", INK3),
                 spacing=S1), 1),
            gauge,
            spacing=S3),
        Label(status, "body", INK2, elide=True),
        # 這一列右邊什麼都不放，說明掛在圖示上——理由見 Shields 的 docstring。
        row(Label("護盾", "caption", INK3),
            Shields(s["saves_total"], s["saves_left"], _saves_tip(d)),
            "stretch",
            spacing=S3),
    )
    return card


def _saves_tip(d):
    """滑過護盾圖示時顯示什麼。

    存滿的時候不講「再達標 N 天多一個」——沒有缺口就沒有要補的東西，
    那句話是在回答沒有人問的問題。但也不該是空的：**這一頁不是設定面板，
    是動機的介面**（熱力圖、連續天數、徽章都在這裡），而護盾全滿本來就是
    一件值得被拍拍肩膀的事。所以這一格給一句話，不給一個數字。

    少了才講數字，而且講的是「再達標幾天」不是「幾號補滿」：護盾靠達標賺回來，
    不靠時間流逝（見 dashboard.SAVE_CAP）。寫成日期會暗示只要等就會回來，
    那是假的。
    """
    s = d["streak"]
    if s["saves_left"] >= s["saves_total"]:
        return "保持水分！"
    return f"還剩 {s['saves_left']} 個，再達標 {s['saves_next_in']} 天多一個"


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
    # 列距用 S3，跟這個視窗其他地方一樣。原本是 S2（8px），六列擠成一團，
    # 每一列有名字與說明兩行，行距 4px——列與列之間只差 8px，掃過去分不出
    # 哪兩行是同一個成就。
    #
    # 這一頁現在剛好等於最高的那一頁（479px），視窗高度不變。**再加第七個
    # 成就就會把整個視窗撐高**，那時要嘛回頭縮這個值，要嘛接受視窗變高。
    card.box.setSpacing(S3)
    for i, (name, desc, cur, goal) in enumerate(dashboard.achievements(d)):
        done = cur >= goal
        card.add(row(
            Badge(done, goal - cur, icon=i),
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

    # 導覽用的（今天／紀錄／成就）維持 40：那是這個視窗的主要動作。
    # 設定裡的分段控制項用 CTRL_H——控制項不該比它標示的內容更搶眼。
    H = 40
    INSET = 4

    def __init__(self, labels, h=None):
        super().__init__()
        self.labels = labels
        self.index = 0
        self.H = h or Segmented.H
        self.setFixedHeight(self.H)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.PointingHandCursor)
        # 選取的藥丸用彈簧滑過去，不是瞬間跳——跟島同一套物理
        self.sp = Spring(0.0, 0.38, 0.85)
        # 矮的那種（設定裡）用小一級的字：框縮了字沒縮，看起來還是很重
        self._f = font("headline" if self.H >= Segmented.H else CTRL_TYPE)
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

        p.setBrush(PAL.ink_a(20))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.H), self.H / 2, self.H / 2)

        w = self.seg_w()
        pill = QRectF(self.INSET + self.sp.value * w, self.INSET, w, self.H - self.INSET * 2)
        # 選中格的底色兩套主題是相反做法，見 theme.Palette.seg_pill
        p.setBrush(PAL.seg_pill)
        p.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)

        fm = QFontMetrics(self._f)
        p.setFont(self._f)
        baseline = int(round(self.H / 2 + (fm.ascent() - fm.descent()) / 2))
        for i, text in enumerate(self.labels):
            # 亮度跟著彈簧的距離插值，切換時是滑過去而不是瞬間換色
            near = clamp(1.0 - abs(self.sp.value - i), 0.0, 1.0)
            p.setPen(PAL.ink_a(int(lerp(150, 255, near))))
            cx = self.INSET + w * (i + 0.5)
            p.drawText(int(cx - fm.horizontalAdvance(text) / 2), baseline, text)


# ---------------------------------------------------------------- 設定頁的元件

class Toggle(Graphic):
    """開關。用彈簧滑過去，跟島與分段控制項同一套物理。

    不用 QCheckBox：勾選框在這張版面裡是唯一一個「作業系統長相」的東西，
    而且它不會動——旁邊每個元件都有彈簧，只有它瞬間跳，會很突兀。
    """

    toggled = Signal(bool)

    W, H = 46, 28

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
        off = PAL.ink_a(30)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(int(lerp(off.red(), C_GREEN.red(), t)),
                          int(lerp(off.green(), C_GREEN.green(), t)),
                          int(lerp(off.blue(), C_GREEN.blue(), t)),
                          int(lerp(off.alpha(), 255, t))))
        p.drawRoundedRect(track, self.H / 2, self.H / 2)

        r = self.H / 2 - 4
        cx = lerp(4 + r, self.W - 4 - r, t)
        # 旋鈕永遠是白的：它壓在綠色軌道或灰色軌道上，底不是頁面底色。
        # 淺色主題若跟著翻成黑色，開啟狀態會變成綠底黑點，讀起來像壞掉。
        p.setBrush(QColor(255, 255, 255, 240))
        p.drawEllipse(QRectF(cx - r, self.H / 2 - r, r * 2, r * 2))


class HourStepper(Graphic):
    """`‹ 08:00 ›` 小時步進器。

    不用系統的時間選擇器：QTimeEdit 會在這片自繪的版面中間開一個 Windows 的洞，
    而且它給到分鐘——這裡只用得到小時，多出來的精度只會讓人以為分鐘有意義。
    """

    changed = Signal(int)

    W, H = 116, CTRL_H
    ZONE = 36           # 左右各留這麼寬當按鈕；圖示只有 8px，點擊區要大得多

    def __init__(self, hour, midnight_as_24=False):
        super().__init__(self.W, self.H)
        self.hour = int(hour) % 24
        # 午夜要寫 24:00 還是 00:00，看這個時刻在句子裡是「開始」還是「結束」。
        # 就寢時間是一天的結束，寫 00:00 會被讀成「今天開始」；起床時間相反，
        # 00:00 就是 00:00。所以由呼叫端指定，不在這裡自作主張。
        self._m24 = midnight_as_24
        self.setCursor(Qt.PointingHandCursor)
        self._f = font(CTRL_TYPE)

    def set_hour(self, hour, emit=True):
        hour %= 24
        if hour == self.hour:
            return
        self.hour = hour
        self.update()
        if emit:
            self.changed.emit(hour)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        x = event.position().x()
        if x < self.ZONE:
            self.set_hour(self.hour - 1)       # 小時是環狀的，0 往下就是 23
        elif x > self.W - self.ZONE:
            self.set_hour(self.hour + 1)

    def wheelEvent(self, event):
        self.set_hour(self.hour + (1 if event.angleDelta().y() > 0 else -1))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setOpacity(clamp(ease(self.reveal), 0.0, 1.0))

        p.setPen(Qt.NoPen)
        p.setBrush(PAL.ink_a(20))
        p.drawRoundedRect(QRectF(0, 0, self.W, self.H), self.H / 2, self.H / 2)

        cy = self.H / 2
        p.setPen(QPen(PAL.ink_a(150), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        # 箭頭要指向它會把數字帶去的方向：左邊的指左、右邊的指右。
        # side=-1 是左鈕，尖端必須在臂的左邊（x 較小）。
        for side in (-1, 1):
            cx = self.ZONE / 2 if side < 0 else self.W - self.ZONE / 2
            tip = cx + side * 3
            arm = cx - side * 2
            p.drawLine(QPoint(int(arm), int(cy - 5)), QPoint(int(tip), int(cy)))
            p.drawLine(QPoint(int(tip), int(cy)), QPoint(int(arm), int(cy + 5)))

        fm = QFontMetrics(self._f)
        text = "24:00" if (self.hour == 0 and self._m24) else f"{self.hour:02d}:00"
        p.setFont(self._f)
        p.setPen(PAL.ink_a(255))
        p.drawText(int(self.W / 2 - fm.horizontalAdvance(text) / 2),
                   int(cy + (fm.ascent() - fm.descent()) / 2), text)


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
        self.setFixedSize(72, CTRL_H)   # 高度也要釘住，否則會被列高拉長
        self.setFont(font(CTRL_TYPE))
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
# 對齊錯了，是每一列的高度都不一樣——有說明的列自己長高、沒說明的列自己縮短，
# 於是右側控制項的中心線每一列都落在不同的地方，眼睛掃下來就是歪的。
#
# 解法是把列高釘死成兩種，兩種都是 8 的倍數，控制項一律垂直置中。

GRID = 8
ROW_TALL = GRID * 7        # 56：有說明的設定列（標題 + 說明兩行）
ROW_FLAT = GRID * 6        # 48：單行的設定列。裡面有控制項，要留得下點擊區
ROW_INFO = GRID * 5        # 40：唯讀資訊列。沒有東西要點，就不需要那個餘裕——
                           #     互動列比資訊列高，是因為滑鼠需要空間，不是為了好看
ROW_SECTION = GRID * 4     # 32：區塊標題

# LABEL_GAP / CTRL_H / CTRL_W 定義在檔案上方的設計常數區——
# 元件類別（Toggle、HourStepper…）比這一段早出現，會用到它們。
#
# 這幾個值先前是 48/40/32/24——那是為了把設定頁擠進 558px 的內容區壓出來的，
# 不是設計判斷。改成可捲動之後就沒有理由再擠。
# 版面被空間逼出來的妥協，要在空間解禁時退回去，不然那些妥協會被
# 後人當成刻意的設計而繼續沿用。
LABEL_RATIO = 0.56         # 標籤欄佔的寬度；其餘留給控制項，右對齊
# C_DIVIDER 由 apply_theme() 設定，這裡不要再寫死一次——
# 寫死的話切換主題時它不會跟著換，淺色版上會留下一條白線。


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

    列高釘死，不讓內容決定——有說明的 48、沒說明的 40。
    高度浮動的話，右側控制項的中心線會每列不同，整欄看起來是歪的。

    左欄用伸展因子吃掉剩餘寬度，不是在旁邊塞 "stretch"：
    那會讓 stretch 把空間搶走，帶省略號的說明被壓成「這是在電腦…」。
    """
    # hint 可以直接傳字串，也可以傳外面先建好的 Label（內容需要之後更新時）
    if hint is None:
        hint_w = None
    elif isinstance(hint, QLabel):
        hint_w = hint
    else:
        hint_w = Label(hint, "caption", INK3, elide=True)
    left = col(Label(label, "headline", INK),
               *([hint_w] if hint_w else []),
               spacing=LABEL_GAP)
    w = row((left, 1), control, spacing=S3, align=Qt.AlignVCenter)
    w.setFixedHeight(ROW_TALL if hint else ROW_FLAT)
    return w


def info_row(label, value, trailing=None, elide_value=False, indent=0):
    """唯讀資訊列：左邊名稱、右邊值。跟設定列共用同一條基線。

    `indent` 把整列往右推，用來表示「這一列屬於上面那一列」。縮排是層級唯一
    看得出來的訊號——同一張卡裡的列預設全部齊左，讀起來就是並列的同級項目。

    `value` 可以是字串，也可以是外面先建好的 Label（需要之後更新內容時）。

    值預設不開省略號，而且靠 "stretch" 推到右邊。
    開了 elide 的 Label 水平政策是 `Ignored`，沒有伸展因子就會被壓成 0 寬度、
    整個消失——「夜間放慢提醒」那一列的值就是這樣不見的，畫面上只剩一個標籤
    跟一段沒頭沒尾的說明，而且沒有任何錯誤。

    只有真的可能過長的值（例如資料夾路徑）才傳 `elide_value=True`，
    那時改用伸展因子吃掉剩餘寬度——要省略的欄位一定要有伸展因子，
    這條規則在 Label 的 docstring 裡寫過，我又踩了一次。
    """
    val = value if isinstance(value, QLabel) else Label(
        value, "body", INK2, elide=elide_value)
    items = [Label(label, "body", INK3)]
    items += [(val, 1)] if elide_value else ["stretch", val]
    if trailing is not None:
        items.append(trailing)
    w = row(*items, spacing=S3, margins=(indent, 0, 0, 0), align=Qt.AlignVCenter)
    w.setFixedHeight(ROW_INFO)
    return w


# 邊緣漸層的高度。28 太厚——它會蓋到「完整顯示、讀得到」的那幾行，
# 把說明段落洗成半透明。遮罩的作用是暗示「還有」，不是把內容變淡，
# 所以只夠在最外緣做出淡出就好。
FADE_H = 18


def scrollbar_qss():
    """捲軸的樣式。跟著主題走，所以是函式不是常數。

    Windows 預設那條捲軸帶著方角、箭頭按鈕與實心軌道，放進這片自繪的版面
    就是一塊作業系統的補丁。這裡只留一根圓角的把手，軌道全透明。

    不要加 `QScrollArea { background: transparent }`。那條規則會讓
    Qt 的樣式表機制把整塊區域擦成透明，蓋掉父層畫好的底色——在半透明視窗上
    那就是一個會讓滑鼠穿透的洞。背景由 ScrollPane 與內容頁自己畫。
    """
    ink = PAL.ink_rgb
    return f"""
        QScrollBar:vertical {{
            background: transparent; width: 10px; margin: 2px 0 2px 0;
        }}
        QScrollBar::handle:vertical {{
            background: rgba({ink[0]},{ink[1]},{ink[2]},0.22);
            border-radius: 3px; min-height: 36px;
            margin: 0 3px 0 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba({ink[0]},{ink[1]},{ink[2]},0.38);
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0; background: transparent;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
    """


class _Fade(QWidget):
    """內容被裁切的那一緣畫一道漸層，暗示「還有」。

    這是這個檔案裡唯一允許捲動的地方所付的代價：不捲動的面板一眼就知道
    有多少東西，捲動的沒有。漸層是把那個資訊還一部分回來——
    邊緣是硬切還是淡出，決定了人會不會想到要往下拉。
    """

    def __init__(self, parent, top):
        super().__init__(parent)
        self.top = top
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedHeight(FADE_H)
        self.hide()

    def paintEvent(self, event):
        p = QPainter(self)
        base = QColor(PAL.bg_top if self.top else PAL.bg_bottom)
        g = QLinearGradient(0, 0, 0, self.height())
        solid, clear = QColor(base), QColor(base)
        clear.setAlpha(0)
        g.setColorAt(0.0, solid if self.top else clear)
        g.setColorAt(1.0, clear if self.top else solid)
        p.fillRect(self.rect(), QBrush(g))


def fill_window_bg(widget, painter):
    """把 widget 自己那一塊填成不透明的視窗底色。

    這是一個嚴重回歸的修正。視窗開了 WA_TranslucentBackground（圓角與陰影
    需要它），而在 Windows 上，完全透明的像素會讓滑鼠事件穿透到下面那個視窗——
    捲動區那一整塊變成一個洞：看起來是透明的，點下去操作到底下的瀏覽器。

    漸層錨在視窗座標而不是 widget 自己的座標。兩個理由：
    一是捲動時背景才不會跟著內容一起移動（那看起來像整面牆在滑）；
    二是接縫——視窗底色是 bg_top → bg_bottom 的漸層，各畫各的會在捲動區
    邊緣留下一條看得見的橫線（深色主題兩端差 14 階）。

    走過的兩條死路，都記在這裡免得有人再試一次：
    - `viewport().setAutoFillBackground(True)`：QAbstractScrollArea 會覆寫視口的
      背景處理，設了沒有用。
    - `setViewport(自繪的 widget)`：視口的 paint 事件先進 viewportEvent()，
      被基底類別吃掉，自訂的 paintEvent 根本不會被呼叫（實測 alpha 全 0）。
    能穩定生效的只有「讓實際覆蓋那塊區域的 widget 自己畫」。
    """
    win = widget.window()
    top = widget.mapTo(win, QPoint(0, 0)).y()
    g = QLinearGradient(0, -top, 0, -top + win.height())
    g.setColorAt(0.0, PAL.bg_top)
    g.setColorAt(1.0, PAL.bg_bottom)
    painter.fillRect(widget.rect(), QBrush(g))


class ScrollPane(QWidget):
    """把一頁內容包成可捲動，並在上下緣加漸層遮罩。

    設定可以捲，紀錄不行。紀錄那三頁是拿來逛的——成就與軌跡藏在捲軸下面
    等於不存在；設定是拿來查的，帶著目的進來、改完就走，捲動是標準做法。
    這條規則從「一律不捲」改成「依頁面性質決定」，理由記在這裡。

    三個子元件用手動座標而不是 layout：漸層是疊在捲動區上面的覆蓋層，
    layout 表達不了重疊關係。這是這個檔案裡少數該手算座標的地方。
    """

    class _Area(QScrollArea):
        """滾輪必須在這一層接。

        QAbstractScrollArea 自己處理 wheel 事件，所以它不會往上傳到 ScrollPane——
        第一版把 wheelEvent 寫在 ScrollPane 上，完全沒有被呼叫過。
        """

        def __init__(self, on_wheel):
            super().__init__()
            self._on_wheel = on_wheel

        def wheelEvent(self, event):
            self._on_wheel(event)

        def scrollContentsBy(self, dx, dy):
            """整塊重畫，不要用平移既有像素的最佳化。

            Qt 預設是把可視區的像素整片平移，只重畫新露出的那一條。而內容頁的
            背景漸層是錨在視窗座標上的（見 fill_window_bg），平移過去就跟新位置
            對不上，所以這裡本來就不該用那個最佳化。這個尺寸的面板重畫整塊，
            成本量不出來。

            這不是「設定頁捲動時版面錯位」那個 bug 的修正。加了之後症狀照舊，
            原因至今未明——版面在每一條路徑上量出來都是對的（371/274/338、
            間距 17px），畫面上卻差了 200px。線索：靜止時空白也不會消失，
            所以不是捲動當下的暫時殘影。
            """
            super().scrollContentsBy(dx, dy)
            self.viewport().update()

    def __init__(self, inner):
        super().__init__()
        self.inner = inner

        self.area = self._Area(self._wheel)
        self.area.setParent(self)
        self.area.setWidget(inner)
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.NoFrame)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.area.setStyleSheet(scrollbar_qss())

        self.top_fade = _Fade(self, top=True)
        self.bottom_fade = _Fade(self, top=False)
        bar = self.area.verticalScrollBar()
        bar.valueChanged.connect(self._sync_fades)
        bar.rangeChanged.connect(self._sync_fades)
        # 使用者直接拖捲軸時，把平滑捲動的目標同步過去，
        # 否則放開之後彈簧會把畫面拉回它自己的舊目標。
        bar.sliderMoved.connect(lambda v: self._sp.snap(float(v)))

        # 平滑捲動：跟島、卡片、分段控制項同一套彈簧物理。
        # 滾輪預設是一格一格跳，在一份要「掃過去找東西」的清單上，
        # 跳動會讓眼睛每次都要重新定位。
        self._sp = Spring(0.0, 0.30, 1.0)      # 阻尼給滿：捲動過頭再彈回來會暈
        self._frame = QTimer(self)
        self._frame.setInterval(16)
        self._frame.timeout.connect(self._step)
        self._last = time.perf_counter()

    def paintEvent(self, event):
        # 捲軸那條 10px 的窄帶不在內容頁的覆蓋範圍內，要由這一層補上底色，
        # 否則那一條會是透明的洞。
        fill_window_bg(self, QPainter(self))

    def set_inner(self, inner):
        """換掉內容（換主題要重建整頁）。

        舊的那一頁由 QScrollArea 自己回收——setWidget() 會接管所有權並刪掉
        前一個 widget。呼叫端不要再 deleteLater()，那會拿到已被回收的 C++ 物件。
        """
        self.inner = inner
        self.area.setWidget(inner)
        self.area.setStyleSheet(scrollbar_qss())
        self._sync_fades()

    def to_top(self):
        self.area.verticalScrollBar().setValue(0)
        self._sp.snap(0.0)

    def _wheel(self, event):
        bar = self.area.verticalScrollBar()
        if bar.maximum() <= 0:
            return
        # 一格滾輪 = 120，換算成三列的高度：跟得上手感又不會一次跳過整段
        delta = event.angleDelta().y() / 120.0 * ROW_FLAT * 3
        self._sp.target = clamp(self._sp.target - delta, 0.0, float(bar.maximum()))
        if not self._frame.isActive():
            self._last = time.perf_counter()
            self._frame.start()

    def _step(self):
        now = time.perf_counter()
        self._sp.step(now - self._last)
        self._last = now
        self.area.verticalScrollBar().setValue(int(round(self._sp.value)))
        if self._sp.settled:
            self._sp.snap()
            self.area.verticalScrollBar().setValue(int(round(self._sp.value)))
            self._frame.stop()

    def _sync_fades(self):
        bar = self.area.verticalScrollBar()
        self.top_fade.setVisible(bar.value() > 2)
        self.bottom_fade.setVisible(bar.value() < bar.maximum() - 2)

    def resizeEvent(self, event):
        self.area.setGeometry(0, 0, self.width(), self.height())
        self.top_fade.setGeometry(0, 0, self.width(), FADE_H)
        self.bottom_fade.setGeometry(0, self.height() - FADE_H, self.width(), FADE_H)
        self._sync_fades()


class DangerRow(QWidget):
    """破壞性動作的入口。只有「說明 + 一顆紅色的觸發」，確認交給 ConfirmOverlay。

    就地確認拿掉了。前一版點一下會原地變成「確定要清除所有紀錄嗎？取消 刪除」，
    問題是確認鍵長在觸發鍵剛剛的位置：實測「刪除」與「清除紀錄」水平重疊 33px，
    兩顆又都靠右對齊。手快點兩下、或第一下沒反應再補一下，第二下就落在「刪除」上，
    而清除紀錄不可復原。這不是機率很低的意外，是版面把它擺在那裡。
    """

    requested = Signal()

    def __init__(self, note, action_text="清除紀錄"):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedHeight(ROW_FLAT)
        self.note = Label(note, "caption", INK3, elide=True)
        self.action = TapLabel(action_text, C_DANGER)
        self.action.clicked.connect(self.requested)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(S3)
        lay.addWidget(self.note, 1)
        lay.addWidget(self.action)


class ConfirmOverlay(QWidget):
    """確認用的小 popup，開在視窗裡面。

    為什麼是 popup 而不是就地確認：見 DangerRow。popup 真正的價值是把確認鍵
    放到游標剛剛不在的地方，順手點不到；蓋住整個視窗則讓它非答不可。

    為什麼不用 QMessageBox：它會在這片自繪的版面中間開一個 Windows 的洞。
    「要不要打斷使用者」跟「要不要用系統元件」是兩件事，前者要、後者不要，
    所以自己畫一個，維持同一套語言。

    取消的路有三條（按鈕、Esc、點卡片外面），刪除只有一條。
    不可復原的動作，兩邊的成本本來就不該對稱。
    """

    accepted = Signal()

    CARD_W = 380
    CORNER = 18

    def __init__(self, parent, title, body, confirm_text="刪除"):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.card = QWidget(self)
        self.card.setAttribute(Qt.WA_TranslucentBackground)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(PAD, PAD, PAD, PAD)
        lay.setSpacing(S3)
        lay.addWidget(Label(title, "headline", INK))
        lay.addWidget(para(body, "caption", INK2))
        self.cancel = TapLabel("取消", INK2)
        self.cancel.clicked.connect(self.dismiss)
        self.confirm = TapLabel(confirm_text, C_DANGER)
        self.confirm.clicked.connect(self._fire)
        lay.addWidget(row("stretch", self.cancel, self.confirm, spacing=S4))
        self.hide()

    # -------------------------------------------------------- 開關

    def ask(self):
        parent = self.parentWidget()
        self.setGeometry(0, 0, parent.width(), parent.height())
        self._layout_card()
        self.show()
        self.raise_()
        self.setFocus(Qt.OtherFocusReason)

    def dismiss(self):
        self.hide()

    def _fire(self):
        self.hide()
        self.accepted.emit()

    # -------------------------------------------------------- 版面與繪製

    def _layout_card(self):
        w = min(self.CARD_W, max(240, self.width() - SHADOW * 2 - PAD * 2))
        h = self.card.layout().heightForWidth(w)
        if h <= 0:
            h = self.card.sizeHint().height()
        self.card.setGeometry(int((self.width() - w) / 2),
                              int((self.height() - h) / 2), w, h)

    def resizeEvent(self, event):
        self._layout_card()

    def mousePressEvent(self, event):
        # 點卡片外面＝取消。只認取消，不認確認——誤觸要落在安全的那一邊。
        if not self.card.geometry().contains(event.position().toPoint()):
            self.dismiss()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.dismiss()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # 遮罩要裁進視窗的圓角裡，不然四個角會冒出四塊直角的暗色。
        body = QRectF(SHADOW, SHADOW, self.width() - SHADOW * 2, self.height() - SHADOW * 2)
        clip = QPainterPath()
        clip.addRoundedRect(body, 22, 22)
        p.setClipPath(clip)
        p.fillRect(body, QColor(0, 0, 0, 150))
        p.setClipping(False)

        card = QRectF(self.card.geometry())
        draw_soft_shadow(p, card, SHADOW_ALPHAS, offset_y=SHADOW_OFFSET_Y,
                         corner=self.CORNER)
        g = QLinearGradient(card.left(), card.top(), card.left(), card.bottom())
        g.setColorAt(0.0, C_CARD_TOP)
        g.setColorAt(1.0, C_CARD_BOTTOM)
        p.setBrush(QBrush(g))
        p.setPen(QPen(PAL.veil(30), 1))
        p.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5),
                          self.CORNER, self.CORNER)


def build_empty_card(d):
    card = Card()
    card.add(
        Label("還沒有紀錄", "title", INK),
        Label("點擊動態島即可記錄補水", "body", INK2, elide=True),
        Label("首次記錄後開始累積", "body", INK3, elide=True),
    )
    return card


# ---------------------------------------------------------------- 設定頁

class SettingsPage(QWidget):
    """設定。刻意開得很窄——篩選標準見 settings.py 開頭。

    這一頁同時是「這個程式在你電腦上做了什麼」的交代處。對發布出去的工具，
    那比控制項更重要：使用者第一個問題是「它有沒有在傳我的資料」，
    而答案必須看得到，不是寫在 README 裡等人去翻。
    """

    changed = Signal(dict)          # 丟出整份新的 cfg
    reset_requested = Signal()      # 使用者按了「清除紀錄」，確認交給視窗
    reset_done = Signal()
    replay_onboarding = Signal()    # 「重看使用說明」，由島負責開那個視窗
    # 主題另外發一個訊號：換主題要把整個視窗重建（文字顏色是在建立 QLabel 時
    # 寫進 stylesheet 的，改模組變數不會回頭修改已存在的元件），
    # 那件事只有 StatsWindow 做得到。
    theme_changed = Signal(str)

    def __init__(self, cfg):
        super().__init__()
        # 不能是半透明的。這一頁是捲動區裡實際覆蓋整個可視範圍的東西，
        # 它不畫背景，那塊區域就是透明的——在半透明視窗上等於一個
        # 會讓滑鼠穿透到底下視窗的洞。見 fill_window_bg()。
        self.cfg = dict(cfg)
        self.cards = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        # 間距一律自己宣告，不靠 layout 的預設值。兩者並存會疊加——
        # 上一版 setSpacing(GAP) 又手動 addSpacing(S4)，每個接縫實際是 40px 而不是 24。
        lay.setSpacing(0)

        # 五組，由上而下就是動線：
        #   你要喝多少 -> 它長什麼樣 -> 它自己判斷了什麼 -> 這程式是什麼 -> 重來
        # 最常動的在最上面，永遠不會動的在最下面，不可復原的在最末端。
        # 先前擠成一張卡是為了塞進 558px，那是妥協不是分類。
        for i, card in enumerate((self._reminder_card(), self._display_card(),
                                  self._about_card())):
            if i:
                lay.addSpacing(GAP)
            self.cards.append(card)
            lay.addWidget(card)

        # 破壞性動作放在卡片外面，用分隔線與一大段留白隔開。
        # 它跟上面那些「調整偏好」在語意上不是同一類東西，放進同一張卡
        # 就會被讀成清單裡的又一列，而滑鼠往下掃的路徑會經過它。
        lay.addSpacing(S5)
        lay.addWidget(Divider())
        lay.addSpacing(S3)
        self.danger = DangerRow("移除所有補水紀錄與連續天數，設定保留")
        # 確認的 popup 由視窗開，不是這一頁——它要蓋住整個視窗，
        # 而這一頁被關在捲動區裡面，蓋不出去。
        self.danger.requested.connect(self.reset_requested)
        lay.addWidget(self.danger)
        lay.addSpacing(S3)

    def paintEvent(self, event):
        fill_window_bg(self, QPainter(self))

    def showEvent(self, event):
        super().showEvent(event)
        # 自訂音效的狀態是檔案系統的事實，程式不會收到通知。每次這一頁被叫出來
        # 就重讀一次——放完檔案回來看，數字是新的。
        self._refresh_sound_label()
        self._fit_cards()

    def resizeEvent(self, event):
        # 每次都重算，不要只在寬度變動時算。第一次 resize 發生在版面排好之前，
        # 那時量到的是還沒收斂的值（實測「顯示」卡量到 318，正確答案是 274），
        # 釘死之後就再也沒有機會更正。
        #
        # 不會遞迴：setFixedHeight 的值沒變就不觸發重排，而卡片版面的 sizeHint
        # 不依賴卡片自己的高度，所以一定收斂。
        super().resizeEvent(event)
        self._fit_cards()

    def _fit_cards(self):
        """每張卡的高度自己算，不交給 QVBoxLayout 分配。

        QVBoxLayout 不會把 heightForWidth 可靠地往下傳。「關於」那張卡裡有兩段
        會換行的說明，實測在 706px 寬時 `heightForWidth` 回 338，但版面的 `sizeHint`
        回 404——兩個差 66px，而版面是照後者去分配的。後果有兩個，使用者兩個都遇到了：

        - 視窗拉窄時，段落多一行、需要更高，版面卻不跟著長，最後一段被切掉
          （截圖裡說明斷在「僅涵蓋使用電」）
        - 多出來的空間被平均塞給前面的卡，顯示卡憑空多了 65px，
          兩張卡中間出現一大塊空白

        所以直接問每張卡「在這個寬度下要多高」，設成固定值。
        沒有 heightForWidth 的卡（內容都是不換行的列）用 sizeHint，那個是準的。
        """
        for card in self.cards:
            lay = card.layout()
            lay.activate()
            if lay.hasHeightForWidth():
                need = lay.heightForWidth(card.width())
            else:
                need = max(lay.sizeHint().height(), lay.minimumSize().height())
            if need > 0:
                card.setFixedHeight(need)

    # ------------------------------------------------------------ 卡片
    #
    # 每張卡的內部間距是 0：列高已經釘死，列與列之間靠分隔線切開。
    # 用間距來分隔會讓「這兩列是同一組嗎」變成猜的；分隔線是明確的答案。

    def _reminder_card(self):
        """喝多少、多久提醒一次、一天從幾點開始算。

        設定項的說明是標籤，不是文案：講清楚「這個值影響什麼」就停，
        不解釋機制、不講理由、不用第二人稱。理由屬於 README，不屬於介面。

        單位（公斤、分鐘）一律貼在控制項右邊，不寫進說明裡——
        單位是那個值的一部分，寫進說明就變成要讀完一句話才知道自己在設什麼。
        """
        card = Card()
        card.box.setSpacing(ROW_GAP)
        card.add(section_header("提醒"))
        card.add(GRID)

        # 每日目標不另立一列，它就是體重這一列的結果——放在說明行，
        # 因果直接可見：填了體重，底下那行當場變成算出來的目標。
        # 先前它是獨立的一列，把「結果」跟「這個值哪來的」用「·」串成三段等重的
        # 碎片，讀的人得自己判斷哪一段重要。
        #
        # 原本掛在這裡的「僅儲存於本機」搬到「關於」——那是使用者會去找隱私
        # 聲明的地方，而說明行該留給結果。
        self.weight = WeightField(self.cfg.get("weight_kg"))
        self.weight.editingFinished.connect(self._on_weight)
        self.target_lbl = Label("", "caption", INK3, elide=True)
        card.add(setting_row("體重", row(self.weight,
                                        Label("公斤", "body", INK3), spacing=S2),
                             self.target_lbl))
        card.add(Divider())

        choices = appsettings.INTERVAL_CHOICES
        self.interval = Segmented([f"{m}" for m in choices], h=CTRL_H)
        self.interval.setFixedWidth(CTRL_W)
        cur = min(range(len(choices)),
                  key=lambda i: abs(choices[i] - self.cfg["interval_min"]))
        self.interval.set_index(cur, animate=False)
        self.interval.index = cur
        self.interval.changed.connect(self._on_interval)
        card.add(setting_row("提醒間隔",
                             row(self.interval, Label("分鐘", "body", INK3), spacing=S2),
                             "以鍵盤滑鼠的活動時間計算"))
        card.add(Divider())

        # 夜間放慢是「提醒間隔」的補充條件，不是另一個主題——它先前自成一張
        # 名為「排程」的卡，一整張只為了顯示一個不能改的值，旁邊還附一段解釋
        # 為什麼睡前不該灌水。使用者看到的是一個讀不出用途的區塊。
        #
        # 放回它所屬的脈絡：緊接在間隔後面，讀起來就是「平常 75 分，晚上改 109 分」。
        # 說明只寫這個數字從哪來，不寫為什麼要有這個機制——理由屬於 README。
        # 這一列問的是就寢時間，不是「夜間幾點開始放慢」。理由跟底下問起床
        # 而不問換日完全相同：後者是系統概念，使用者得自己反推（「我兩點睡，
        # 減三小時，所以填 23 點」）；就寢時間是他本來就知道的事實。
        # 深夜起點是它的導出值，寫在說明裡當結果看，不再是可以獨立亂設的參數。
        self.bedtime = HourStepper(
            self.cfg.get("bedtime_hour", appsettings.DEFAULTS["bedtime_hour"]),
            midnight_as_24=True)
        self.bedtime.changed.connect(self._on_bedtime)
        # hint 傳 Label 而不是字串：間隔改了、就寢改了，這行都要跟著重算。
        self.late_lbl = Label(self._late_text(), "caption", INK3, elide=True)
        self.bed_auto = TapLabel("改為自動", C_ACCENT.name())
        self.bed_auto.clicked.connect(self._back_to_auto)
        card.add(setting_row("預計就寢時間",
                             row(self.bed_auto, self.bedtime, spacing=S3),
                             self.late_lbl))
        card.add(Divider())

        # 「習慣起床時間」原本在這裡，2026-08-22 拿掉了。
        #
        # 它一路在掉職責：先是不再決定換日（訂死在早上 5 點），再來是不再決定
        # 夜間模式什麼時候結束（改綁換日那個常數，見 island._is_late）。最後
        # 只剩「推算就寢時間」，而就寢時間就在上面那一列、可以直接設——
        # **問兩個值去推一個值，而那個值本來就問得到。**
        #
        # 面板的篩選標準是「不改就會讓工具對這個人失效」。推錯了也只影響
        # 就寢時間的初始建議，而那個建議使用者當場就能改掉，所以它過不了那條線。
        # 值本身還在（由活動紀錄推導），只是不再要人回答。

        # 放在「提醒」而不是「顯示」：它管的是提醒怎麼傳到人身上，
        # 不是介面長什麼樣子。放進顯示卡會讀成一個外觀偏好。
        #
        # 說明行要寫出「什麼時候才響」。不寫的話這一列看起來就是「每次提醒都
        # 會叫」，而多數人對那件事的反應是先關掉再說——一天七聲的想像
        # 遠比實際情況吵。實際上它一天最多響幾次，多數日子是零。
        self.sound = Toggle(self.cfg.get("sound_enabled", True))
        self.sound.toggled.connect(self._on_sound)
        # 說明只講「不是每次提醒都響」。確切的時機交給底下那兩列——
        # 它們的標題就是時機，寫在這裡等於同一件事講兩遍。
        card.add(setting_row("提醒音效", self.sound, "僅於提醒被忽略時發出"))
        card.add(Divider())

        # 兩個升級各一列。用「什麼時候響」當標題，不用「虛弱／倒地」——
        # 那是島的狀態名，在設定頁裡沒有上下文，讀的人不知道那是幾分鐘。
        #
        # 每一列都有「試聽」。這一整區真正的問題不是「要不要有聲音」，
        # 是「那是什麼聲音、多大聲」，而那件事讀說明沒有用，聽一次就知道。
        self._sound_rows = {}
        for i, (name, mins) in enumerate((
                (sound.WEAK, self.cfg.get("escalate_weak_min",
                                          appsettings.DEFAULTS["escalate_weak_min"])),
                (sound.COLLAPSED, self.cfg.get(
                    "escalate_collapsed_min",
                    appsettings.DEFAULTS["escalate_collapsed_min"])))):
            if i:
                card.add(Divider())
            card.add(self._sound_file_row(name, f"忽略 {mins} 分鐘後"))
        self._refresh_target_label()
        self._refresh_schedule_labels()
        return card

    def _sound_file_row(self, name, label):
        """一個音效一列：現在用哪個檔、試聽、選檔、還原。

        「還原」只在真的有自訂檔時才出現。永遠掛在那裡的話，沒換過音效的人
        會對著一個按下去毫無反應的字，而它旁邊兩個都有反應。
        """
        val = Label("", "body", INK2, elide=True)
        test = TapLabel("試聽", C_ACCENT.name())
        test.clicked.connect(lambda n=name: sound.play(n))
        pick = TapLabel("選擇", C_ACCENT.name())
        pick.clicked.connect(lambda n=name: self._pick_sound(n))
        reset = TapLabel("還原", INK3)
        reset.clicked.connect(lambda n=name: self._reset_sound(n))
        self._sound_rows[name] = (val, reset)
        self._refresh_sound_row(name)
        # 縮排：這兩列是「提醒音效」的子項，不是跟它並列的設定。
        # 沒有縮排的話，一張卡裡四列齊左，看起來是四個同級的東西。
        return info_row(label, val, row(test, pick, reset, spacing=S3),
                        elide_value=True, indent=S3)

    def _sound_row_text(self, name):
        """那一列的值。回報事實，不給指示。

        三種狀態要分得開，因為它們對應三種完全不同的處置：
        內建（沒換過）、自訂（正常）、格式不對（換了但沒生效）。
        第三種最重要——沒有它，使用者要等到提醒真的響了才會發現沒換成功，
        而那時候他也分不出是檔案錯了還是程式沒讀到。
        """
        for n, ok in sound.custom_files():
            if n != name:
                continue
            if not ok:
                return "不是 WAV 格式，仍使用內建"
            return self.cfg.get(f"sound_name_{name}") or "自訂"
        return "內建"

    def _refresh_sound_row(self, name):
        pair = self._sound_rows.get(name)
        if not pair:
            return
        val, reset = pair
        val.setText(self._sound_row_text(name))
        reset.setVisible(any(n == name for n, _ in sound.custom_files()))

    def _refresh_sound_label(self):
        for name in getattr(self, "_sound_rows", {}):
            self._refresh_sound_row(name)

    def _pick_sound(self, name):
        """選一個音檔。挑完複製一份進來，不記路徑——理由見 sound.py 開頭。

        用 QFileDialog 而不是自繪。這跟先前把 QMessageBox 換掉不衝突：
        確認框只有一句話跟兩顆鈕，自己畫比蓋掉系統外觀還省；
        而檔案選擇器是作業系統的服務（瀏覽、最近開啟、捷徑、網路磁碟機），
        重寫一個只會做出一個比較差的版本。
        """
        start = os.path.expanduser("~")
        picked, _ = QFileDialog.getOpenFileName(
            self, "選擇提醒音效", start, "音效檔 (*.wav)")
        if not picked:
            return                              # 按了取消，什麼都不動
        if sound.install(name, picked):
            self.cfg[f"sound_name_{name}"] = os.path.basename(picked)
            self._emit()
            self._refresh_sound_row(name)
            sound.play(name)                    # 換好就放給他聽，不必再按一次試聽
            return
        # 驗不過：舊的設定原封不動，把原因寫在值的位置。
        # 這一行會在下次打開設定頁時被實際狀態蓋掉（見 showEvent），
        # 那是對的——錯誤訊息講的是「剛才那個動作」，不是持續的狀態。
        val, _reset = self._sound_rows[name]
        val.setText("選的檔案不是 WAV 格式")

    def _reset_sound(self, name):
        sound.remove(name)
        self.cfg[f"sound_name_{name}"] = ""
        self._emit()
        self._refresh_sound_row(name)

    def _display_card(self):
        card = Card()
        card.box.setSpacing(ROW_GAP)
        card.add(section_header("顯示"))
        card.add(GRID)

        modes = (("auto", "跟隨系統"), ("light", "淺色"), ("dark", "深色"))
        self._theme_keys = [m[0] for m in modes]
        self.theme_seg = Segmented([m[1] for m in modes], h=CTRL_H)
        self.theme_seg.setFixedWidth(CTRL_W)
        cur = self._theme_keys.index(self.cfg.get("theme", "auto")) \
            if self.cfg.get("theme", "auto") in self._theme_keys else 0
        self.theme_seg.set_index(cur, animate=False)
        self.theme_seg.index = cur
        self.theme_seg.changed.connect(self._on_theme)
        card.add(setting_row("外觀", self.theme_seg))
        card.add(Divider())

        screens = QApplication.screens()
        if len(screens) > 1:
            self._screens = screens
            self.screen_seg = Segmented([f"螢幕 {i + 1}" for i in range(len(screens))],
                                        h=CTRL_H)
            self.screen_seg.setFixedWidth(min(CTRL_W, 76 * len(screens)))
            cur = 0
            for i, s in enumerate(screens):
                if s.name() == self.cfg.get("screen_name"):
                    cur = i
            self.screen_seg.set_index(cur, animate=False)
            self.screen_seg.index = cur
            self.screen_seg.changed.connect(self._on_screen)
            g = screens[cur].geometry()
            self.screen_lbl = Label(f"{g.width()}×{g.height()}", "caption", INK3,
                                    elide=True)
            card.add(setting_row("動態島顯示在", self.screen_seg,
                                 f"{g.width()}×{g.height()}"))
        else:
            # 只有一個螢幕時不放控制項：單一選項的選擇器是雜訊，
            # 它讓人以為有得選，點下去才發現沒有。
            g = screens[0].geometry() if screens else None
            card.add(setting_row("動態島顯示在",
                                 Label(f"{g.width()}×{g.height()}" if g else "—",
                                       "body", INK2)))
        card.add(Divider())

        self.autostart = Toggle(appsettings.autostart_enabled())
        self.autostart.toggled.connect(self._on_autostart)
        # 說明只標示這個開關控制什麼。關掉之後怎麼手動開啟，是使用者的常識，
        # 不是這一列的職責——介面把它寫出來就變成在教學。
        card.add(setting_row("開機時啟動", self.autostart))
        card.add(Divider())

        self.check_updates = Toggle(self.cfg.get("check_updates", True))
        self.check_updates.toggled.connect(self._on_check_updates)
        card.add(setting_row("檢查更新", self.check_updates,
                             "啟動時向 GitHub 查詢新版本"))
        return card

    def _about_card(self):
        """對發布出去的工具，這一區比控制項更重要：
        使用者第一個問題是「它有沒有在傳我的資料」，答案要看得到。
        """
        card = Card()
        card.box.setSpacing(ROW_GAP)
        card.add(section_header("關於"))
        card.add(GRID)

        open_lbl = TapLabel("開啟", C_ACCENT.name())
        open_lbl.clicked.connect(self._open_data_dir)
        card.add(info_row("資料位置", appsettings.DATA_DIR, open_lbl))
        card.add(Divider())
        # 齒輪上那顆點只說「有東西要看」，這一列說「是什麼、怎麼拿」。
        # 不另外開一列——這一列本來就是講版本的，有新版正是版本的一部分。
        _newer = updates.checker.newer_release()
        if _newer:
            _tag, _url = _newer
            _get = TapLabel("開啟", C_ACCENT.name())
            _get.clicked.connect(lambda: self._open_url(_url))
            # tag 帶 v 前綴（v0.11.0），顯示時拿掉：畫面上的版本一律不帶 v，
            # 同一列出現兩種寫法會讓人以為是兩個不同的東西。
            card.add(info_row("版本",
                              f"{appsettings.VERSION}（有新版 {_tag.lstrip('vV')}）",
                              _get))
        else:
            card.add(info_row("版本", appsettings.VERSION))
        card.add(Divider())

        # 回報的路要在程式裡，不能只寫在 README——出問題的人正在用程式，
        # 不會為了找一個連結跑去 GitHub。
        #
        # 開瀏覽器而不是在 app 裡做表單：做表單就等於程式要自己送資料出去，
        # 而上面那句「不蒐集也不傳送」不能為了一個回報按鈕破例。
        #
        # 「複製診斷資訊」跟回報是一組的。沒有它，收到的 issue 會是「壞掉了」；
        # 有了它，使用者貼上來的是版本、Windows 版本、螢幕與縮放、崩潰摘要。
        # 一樣不自動送——複製到剪貼簿，貼不貼、貼哪裡都是使用者決定。
        report = TapLabel("開啟", C_ACCENT.name())
        report.clicked.connect(self._open_issues)
        card.add(info_row("回報問題", "GitHub Issues", report))
        card.add(Divider())

        self._diag_lbl = TapLabel("複製", C_ACCENT.name())
        self._diag_lbl.clicked.connect(self._copy_diagnostics)
        # 值的欄位寫「這是什麼」，不寫指示。同一張卡的其他列都是這樣——
        # 資料位置是路徑、版本是號碼、回報問題是去處。而「回報時附上這段」
        # 除了語域不對（「這段」是口語的指稱），也把指示塞進了描述的位置。
        # 這一列就在「回報問題」正下方，該附上什麼不必再講一次。
        card.add(info_row("診斷資訊", "系統與版本資訊", self._diag_lbl))
        card.add(Divider())

        # 引導只在第一次啟動時跑，忘記怎麼用的人需要一條回去的路。
        #
        # 叫「使用導覽」不叫「使用說明」：打開來的是五頁的互動導覽、最後還要
        # 真的點一次島，不是一份文件。而且引導自己的出口就寫「略過導覽」，
        # 同一個東西在兩個地方要用同一個名字。
        #
        # 動作寫「再看一次」。看得到這一列的人一定看過了——沒跑完引導的人
        # 根本進不到設定，所以「開始」是假的，那也正好是引導最後一頁那顆按鈕
        # 的字，兩邊會撞名。
        # 而「重看」雖然意思對，中文介面裡不會這樣講：它是口語的縮寫，
        # 讀起來像講到一半。動作標籤要是完整的動詞片語。
        again = TapLabel("再看一次", C_ACCENT.name())
        again.clicked.connect(self.replay_onboarding)
        card.add(info_row("使用導覽", "", again))
        card.add(GRID)
        # 隱私聲明放這裡而不是體重欄底下：這是使用者會主動來找的地方，
        # 而輸入欄的說明行該留給那一欄的結果。
        # 不能寫「本程式無網路連線」：引導裡有一個彩蛋會用瀏覽器開影片。
        # 那句話會變成假的，而隱私聲明只要有一句不精確，整段就不值得信。
        # 「不蒐集也不傳送」才是真正成立、而且是使用者真正在意的那件事。
        card.add(para("本程式不蒐集也不傳送任何資料，全部僅儲存於本機。"))
        card.add(para("每日目標依國民健康署的公開資料與體重推算，不構成醫療建議。"
                      "僅涵蓋使用電腦期間，未計入運動或流汗的額外需求。"))
        return card

    def _schedule_note(self):
        """深夜模式的起點是怎麼來的。不能一律標「自動判定」——
        資料還不夠時用的是回退值，標成自動判定就是介面在說謊。
        """
        # 使用者自己設過就寢時間就不再是推算的——這裡要先擋掉，否則資料不夠時
        # 會對著他親手填的值說「推估值」。
        if not self.cfg.get("auto_schedule", True) or self.cfg.get("bedtime_manual"):
            return "手動指定"
        # 有沒有夠多天的資料可以取中位數，決定了它是真的算出來的還是猜的
        wake = self.cfg.get("day_rollover_hour", 8)
        fallback = (wake - 11) % 24
        if appsettings.infer_late_hour(appsettings.EVENTS_PATH, wake) != fallback:
            return "依活動紀錄推算"
        return "推估值，累積足夠紀錄後自動校準"

    # ------------------------------------------------------------ 事件

    def _emit(self):
        appsettings.save_config(self.cfg)
        self.changed.emit(dict(self.cfg))

    def _refresh_target_label(self):
        t = appsettings.effective_target(self.cfg)
        ml = t * self.cfg.get("ml_per_drink_estimate", 200)
        src = "由體重推算" if self.cfg.get("weight_kg") else "預設值"
        self.target_lbl.setText(f"{src}：每日目標 {t} 次，約 {ml} cc")

    def _on_weight(self):
        kg = self.weight.value()
        if kg == self.cfg.get("weight_kg"):
            return
        self.cfg["weight_kg"] = kg
        self.cfg["daily_target_drinks"] = appsettings.effective_target(self.cfg)
        self._refresh_target_label()
        self._emit()

    def _on_bedtime(self, hour):
        """改了就寢時間。深夜起點是它的導出值，當場重算。

        設了就標記手動，之後不再被推導覆蓋——跟起床時間同一套規則。
        推導只負責給初始值，使用者一旦表態就聽他的。
        """
        self.cfg["bedtime_hour"] = hour
        self.cfg["bedtime_manual"] = True
        self.cfg["late_night_start_hour"] = appsettings.late_start_from_bedtime(hour)
        self._refresh_late_label()
        self._emit()

    def _on_interval(self, i):
        self.cfg["interval_min"] = appsettings.INTERVAL_CHOICES[i]
        self._refresh_late_label()      # 深夜間隔是主間隔的倍數，會跟著變
        self._emit()

    def _back_to_auto(self):
        """把某一項作息交還給推導。

        使用者的話：「我都設定 02:00/10:00，但最近比較早起，可是看到設定不一樣
        會有點煩」——手動設過的值不會跟著生活變，而**先前沒有任何一條路可以
        改回自動**（`*_manual` 一旦是 True 就永遠是 True，只能去改 config.json）。
        設定進得去出不來，那不是設定，是單向門。

        清掉旗標之後立刻重推一次並更新畫面。不重推的話使用者按完什麼都沒發生，
        要等到下次啟動才看得到——而那時候他已經認定這顆按鈕壞了。
        """
        self.cfg["bedtime_manual"] = False
        appsettings.apply_auto_schedule(self.cfg, appsettings.EVENTS_PATH)
        # emit=False 是關鍵——發訊號會被 _on_bedtime 當成使用者手動設定，
        # 於是「改為自動」這個動作自己把旗標又設回 True。
        self.bedtime.set_hour(self.cfg["bedtime_hour"], emit=False)
        self._refresh_schedule_labels()
        self._emit()

    def _refresh_schedule_labels(self):
        """就寢那一列的說明與「改為自動」的顯示與否。"""
        self.late_lbl.setText(self._late_text())
        # 已經是自動的就不放「改為自動」——按下去不會有事的東西不該出現。
        self.bed_auto.setVisible(bool(self.cfg.get("bedtime_manual")))

    def _late_text(self):
        """深夜放慢這列顯示什麼。

        **講規則，不講算出來的時刻。**

        先前寫的是「23:00 起改為每 86 分」。那個 23:00 是深夜起點，由這一列的
        就寢時間往前推 3 小時算出來的——問題是同一列的控制項上已經有一個時間
        （02:00），兩個時刻擺在一起，讀的人得先分辨哪個是他設的、哪個是算的。
        使用者的原話：「才不會跟設定造成誤會」。

        改成「睡前 3 小時起改為每 86 分」之後，那一行只剩一個數字要讀，
        而且它講的是**規則**——規則不會因為使用者改了就寢時間而失效，
        23:00 會。

        （這裡一度反過來想：把導出的時刻寫出來，使用者才看得到程式假設他
        幾點睡。那個顧慮在就寢時間還沒上面板時是對的，現在它就在同一列的
        控制項裡，假設本來就看得見。）
        """
        mins = appsettings.late_night_interval(self.cfg)
        tail = f"睡前 {appsettings.LATE_BEFORE_SLEEP_H} 小時起改為每 {mins} 分"
        # 這個值是誰決定的要寫出來。使用者的抱怨是「為什麼每次打開都不一樣」
        # ——自動推算的值本來就會隨著紀錄變，但畫面上看不出它是自動的，
        # 於是那個變動讀起來像壞掉。標出來之後，會變就變得合理。
        if self.cfg.get("bedtime_manual"):
            return f"手動指定，{tail}"
        if self._schedule_note().startswith("推估"):
            return f"推估值，累積足夠紀錄後自動校準，{tail}"
        return f"依活動紀錄推算，{tail}"

    def _refresh_late_label(self):
        self._refresh_schedule_labels()

    def _on_theme(self, i):
        self.cfg["theme"] = self._theme_keys[i]
        self._emit()
        self.theme_changed.emit(self.cfg["theme"])

    def _on_screen(self, i):
        self.cfg["screen_name"] = self._screens[i].name()
        self._refresh_screen_label()
        self._emit()

    def _refresh_screen_label(self):
        s = self._screens[self.screen_seg.index]
        g = s.geometry()
        self.screen_lbl.setText(f"{g.width()}×{g.height()}")

    def _on_sound(self, on):
        """開關就只是開關。

        先前扳開會順便播一次當作試聽，那是在沒有試聽鍵的時候的權宜之計。
        底下兩列各有一顆「試聽」之後，開關再自己出聲就變成一個沒被要求的
        副作用——而且它只播得出其中一個音。
        """
        self.cfg["sound_enabled"] = on
        self._emit()

    def _on_check_updates(self, on):
        """下次啟動才生效。**不當場去查。**

        使用者剛扳開它，畫面上不會有任何反應（查詢在背景、要幾秒、而且多半
        查完發現已經是最新版），於是那個開關看起來像壞的。要嘛就得為它做
        「查詢中／已是最新」的即時回饋，那是為了一個一年按一次的開關長出
        一整套狀態顯示。下次啟動再查就好。
        """
        self.cfg["check_updates"] = on
        self._emit()

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

    @staticmethod
    def _open_url(url):
        """用 QDesktopServices 而不是 webbrowser.open()。

        `dashboard.py` 開頭記過那個坑：這台機器的 `.html` 關聯到已經退場的
        Internet Explorer，`webbrowser.open()` 會靜默失敗——什麼都沒發生，
        也查不出來。QDesktopServices 走的是預設瀏覽器，不是副檔名關聯。
        """
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(url))

    def _open_issues(self):
        self._open_url(appsettings.ISSUES_URL)

    def diagnostics(self):
        """回報時要附的那段。**只有機器的規格與程式的狀態，沒有喝水紀錄。**

        判準是「這一項能不能幫忙修 bug」。次數、時間、連續天數都不能，
        那是使用者的生活作息，不該因為按了一顆按鈕就進到剪貼簿裡等著被貼出去。
        """
        import platform

        import crashlog
        # 用介面上的名字，不要把 config 的原始值倒出來。
        # 「主題 dark／臉 pixel」這種寫法有兩個問題：設定頁那一列叫「外觀」
        # 不叫「主題」，同一個東西在兩個地方用不同名字；而「臉」是隨手造的
        # 口語詞，介面上根本沒有。使用者看不懂自己貼出去的是什麼。
        THEME = {"auto": "跟隨系統", "light": "淺色", "dark": "深色"}
        FACE = {"pixel": "像素", "geometry": "幾何"}
        scr = QApplication.primaryScreen()
        screens = QApplication.screens()
        lines = [
            f"Sipbar {appsettings.VERSION}",
            f"Windows {platform.version()}（{platform.machine()}）",
            f"Python {platform.python_version()}",
            # Qt 版本要報。攜帶版把整套 Qt 凍在包裡，使用者自己更新不了，
            # 所以 Qt 出了安全性修正時，唯一能回答「誰拿到了哪一版」的地方
            # 就是這一行。requirements.txt 只寫下界（>=6.11），同一個 commit
            # 在不同時間建出來可能夾帶不同版本。
            f"Qt {qVersion()}（PySide6 {PySide6.__version__}）",
            f"螢幕 {len(screens)} 個，主要 "
            f"{scr.geometry().width()}×{scr.geometry().height()}，"
            f"縮放 {scr.devicePixelRatio() * 100:.0f}%",
            f"字體 {'內嵌' if typeface.ensure_loaded()[0] else '系統替代'}",
            f"外觀 {THEME.get(self.cfg.get('theme'), self.cfg.get('theme'))}，"
            f"角色 {FACE.get(self.cfg.get('face_style'), self.cfg.get('face_style'))}",
            # 只放推導出來的目標，**不放體重**。體重是個人健康資料，而且目標
            # 已經是它算出來的結果，對修 bug 沒有額外資訊——這一段會被貼進
            # 公開的 issue 裡。
            f"每日目標 {appsettings.effective_target(self.cfg)} 次"
            f"（{'依體重推導' if self.cfg.get('weight_kg') else '預設'}）",
            f"提醒間隔 {self.cfg.get('interval_min')} 分鐘",
            f"崩潰紀錄 {crashlog.summary()}",
            # 檢查更新失敗時是安靜的（沒網路、被限流、GitHub 改了回傳格式都
            # 一律安靜放棄）。沒有這一行的話，它哪天靜靜停止運作不會有人發現。
            f"檢查更新 {updates.checker.status()}",
            # 寫入健康狀態。這一行是給「紀錄怎麼少了一段」那種回報用的：
            # 寫檔失敗會被安靜吞掉（不吞的話程式會崩潰，那更糟），所以
            # 畫面上一切正常、資料卻沒存進去。沒有這一行就查不出來。
            # 要講得出是**哪一個**檔案在失敗。只報一個次數的話，回報者只能說
            # 「紀錄好像不見了」，而設定、狀態、紀錄三個檔壞掉的症狀完全不同。
            f"寫入失敗 連續 {appsettings.write_fail_streak()} 次"
            + (f"（{'、'.join(appsettings.failing_writes())}）"
               if appsettings.failing_writes() else ""),
            # 資料檔的實際狀況。使用者回報「紀錄不見了」「數字不對」的時候，
            # 第一個要分辨的是「程式讀不到檔案」還是「讀到了但算錯」——
            # 而那兩件事從畫面上長得一模一樣。
            self._data_file_line(),
        ]
        # 設定檔手改壞掉的欄位。讀不出數字的值會被退回預設，而退回之後畫面上
        # 一切正常——值是合法的，島照跑——使用者只會覺得「我明明改了卻沒有
        # 用」。沒有這一行，那個疑惑在回報裡查不出來。
        if appsettings.repaired_keys():
            lines.append("設定值退回預設 "
                         + "、".join(appsettings.repaired_keys()))
        return "\n".join(lines)

    def _data_file_line(self):
        """兩條路徑各報一次，因為它們有可能不一樣。

        `settings.EVENTS_PATH` 是設定頁「資料位置」那一列顯示的來源；
        紀錄視窗讀的則是 `island.EVENTS_PATH` 傳進來的那一份。兩個模組各有一份
        同名的變數，正常情況下相同——但如果哪天不同，畫面上會是「路徑看起來對、
        數字卻不對」，而那從外面完全看不出來。
        """
        home = os.path.expanduser("~")

        def show(p):
            """把家目錄換成 %USERPROFILE%。

            這一段是給人貼進**公開的** issue 的（旁邊就是「回報問題」），
            而路徑裡的 Windows 帳號名稱，在個人電腦上經常就是本名。

            遮掉不影響診斷力：要分辨的是**路徑後半段對不對**——沙箱重導向那次，
            差別在家目錄之後多插了一段容器資料夾，而那一段照樣看得見。
            """
            if home and os.path.normcase(p).startswith(os.path.normcase(home)):
                return "%USERPROFILE%" + p[len(home):]
            return p

        def stat(p):
            # 只報大小，不報筆數。筆數是使用量，而這個函式上面那條規矩
            # （「沒有喝水紀錄」）本來就把使用量排除在外——先前這裡是自己
            # 破了自己的規矩。分辨「空的／有東西／是另一份」大小一樣夠用。
            try:
                if not os.path.exists(p):
                    return "不存在"
                return f"{os.path.getsize(p)} bytes"
            except Exception as e:                        # noqa: BLE001
                return f"讀取失敗 {type(e).__name__}"

        a = appsettings.EVENTS_PATH
        b = getattr(self, "_events_path", None)
        out = [f"資料檔 {show(a)} → {stat(a)}"]
        if b and os.path.normcase(b) != os.path.normcase(a):
            out.append(f"視窗實際讀 {show(b)} → {stat(b)}")
        return "\n".join(out)

    def _copy_diagnostics(self):
        QApplication.clipboard().setText(self.diagnostics())
        # 剪貼簿是看不見的，沒有回饋的話使用者不知道按到了，就會一直按。
        self._diag_lbl.setText("已複製")
        QTimer.singleShot(1600, lambda: self._diag_lbl.setText("複製"))

    def _on_reset(self):
        """確認已經由視窗的 ConfirmOverlay 問過了，這裡只負責執行。"""
        appsettings.reset_data()
        self.reset_done.emit()


# ---------------------------------------------------------------- 視窗

class StatsWindow(QWidget):
    def __init__(self, cfg, events_path, on_config=None, on_replay=None):
        super().__init__()
        # 一定要複製一份。直接持有島傳來的字典，設定頁改完之後
        # `self.cfg.update(...)` 會就地改掉島的狀態——島的 apply_config()
        # 再去算「哪些鍵變了」時，舊值早就是新值，於是判定沒有變動、提早 return，
        # 換螢幕、改目標這些需要副作用的設定就完全失效（而且沒有任何錯誤）。
        # 擁有權：島擁有它的 cfg，視窗拿一份副本編輯，改完往上回報。
        self.cfg = dict(cfg)
        self.events_path = events_path
        self.on_config = on_config
        self.on_replay = on_replay
        self.mode = "stats"
        self._stats_stale = False     # 設定改過，回紀錄那邊時要重算
        self._drag = None
        self._closing = False
        self._confirm = None          # 確認用的 popup，按下「清除紀錄」才建
        self.cards = []

        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 這個視窗裡所有的提示都走自繪的 Tip，不走 QToolTip——立刻出現、
        # 跟介面同一套外觀、也不受「視窗必須是作用中」那條限制影響。
        # 完整理由見 Tip 的 docstring。
        #
        # `WA_AlwaysShowToolTips` 是上一版為了讓 setToolTip() 在非作用中視窗上
        # 也能出現而加的。那條路已經整條換掉，屬性跟著拿掉——留著一個沒有東西
        # 依賴的設定，下一個人會去猜它在防什麼。
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
        self.settings_page = self._make_settings_page()
        self.pane = ScrollPane(self.settings_page)

        self.root = QStackedWidget()
        self.root.setAttribute(Qt.WA_TranslucentBackground)
        self.root.addWidget(stats_side)
        self.root.addWidget(self.pane)

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
            self._settle(self.cards)
            self.sp_win.snap(1.0)
            self.setWindowOpacity(1.0)

    def _fit_height(self):
        """視窗高度收到「最高那一頁」剛好放得下。

        不捲動的面板一定要這樣做，否則短的頁面底下會留一大塊空白，
        看起來像壞掉或沒做完（實測沿用舊的 900 高，三頁各空了約 200px）。
        高度固定在最高頁，換頁時視窗不會跳動。

        高度要問版面引擎，不要自己加總。手算標題、間距、分段控制項再加起來，
        等於把同一份版面算第二次——第一版就是這樣少算了 64px，三頁全部放不下。
        `QStackedWidget` 的 sizeHint 本來就是所有頁面的最大值，正好是我們要的。

        設定頁不另外算高度，一律沿用紀錄那一側的。點齒輪是換內容，不是開另一個
        視窗；高度一跳，讀起來就像視窗關掉又開了一個新的。所以量的永遠是紀錄那一側，
        設定頁必須把內容收進同一個內容區——收不進去代表設定頁話太多，
        該刪的是字不是把視窗拉長。render_settings.py 會在放不下時擋下來。
        """
        # 量的時候一定要讓紀錄那一側是「目前頁」。
        # QStackedWidget 會把非當前頁 hide 掉，而 layout 對 hidden 的 widget
        # 一律回報 sizeHint 0——在設定模式下量 index 0，會量到 64px，
        # 整個視窗縮成 277px、卡片被壓成 13px 高、文字疊在一起。
        # 兩次 setCurrentIndex 在同一個同步呼叫裡完成，Qt 不會在中間重繪，看不到閃動。
        keep = self.root.currentIndex()
        self.root.setCurrentIndex(0)
        try:
            for i in range(self.root.count()):
                w = self.root.widget(i)
                # 高度永遠由紀錄那一側決定，跟使用者現在看哪一頁無關。
                w.setSizePolicy(QSizePolicy.Preferred,
                                QSizePolicy.Preferred if i == 0 else QSizePolicy.Ignored)
                # 巢狀的 layout 要自己 activate 一次。外層 activate() 不會遞迴下去，
                # 沒 activate 的容器其 sizeHint 是還沒算過的 (0, 0)。
                if w.layout():
                    w.layout().activate()
            self.root.adjustSize()
            lay = self.layout()
            lay.activate()
            need = lay.sizeHint().height()
        finally:
            self.root.setCurrentIndex(keep)
        self.setFixedHeight(need)
        return need

    def _make_settings_page(self):
        page = SettingsPage(self.cfg)
        # 診斷資訊要能比對「設定頁認為的路徑」與「這個視窗實際讀的路徑」。
        page._events_path = self.events_path
        page.changed.connect(self._on_config_changed)
        page.reset_requested.connect(self._ask_reset)
        page.reset_done.connect(self._on_reset_done)
        page.theme_changed.connect(self._on_theme_changed)
        page.replay_onboarding.connect(self._on_replay_onboarding)
        return page

    def _on_replay_onboarding(self):
        """引導視窗由島開，不是這裡開：它結束時要讓真的動態島打招呼，
        而那顆島只有島自己拿得到。"""
        if self.on_replay:
            self.close()
            self.on_replay()

    def _on_theme_changed(self, name):
        """換主題要把整個視窗重建。

        顏色分兩種：自繪的部分讀模組變數，換了就跟著換；但文字顏色是在
        建立 QLabel 的當下寫進 stylesheet 的，改模組變數不會回頭修改已存在的元件。
        與其記住哪些要手動刷、哪些不用（那種清單一定會漏），不如整頁重建——
        設定頁只有五張卡，重建的成本遠低於漏掉一處造成的「一半深色一半淺色」。
        """
        apply_theme(name)
        # 不要自己刪舊的那一頁：QScrollArea.setWidget() 會接管所有權並把
        # 前一個 widget 刪掉，再 deleteLater() 一次會拿到已經被回收的 C++ 物件。
        self.settings_page = self._make_settings_page()
        self.pane.set_inner(self.settings_page)

        # 視窗自己的外框也要換。標題與副標是 QLabel，顏色寫在 stylesheet 裡，
        # 重建設定頁不會動到它們——第一版就是這樣：切到淺色之後底色變白了，
        # 標題還留著深色主題的淺色文字，等於消失。
        self._restyle_chrome()

        if self.mode == "settings":
            self.cards = self.settings_page.cards
            self._settle(self.cards)
        self._stats_stale = True        # 紀錄那三頁離開設定頁時再重建
        self.update()

    def _restyle_chrome(self):
        """把視窗外框（標題、副標）的顏色套成目前主題。

        自繪的部分（分段控制項、關閉鈕、卡片）讀模組變數，換主題自動跟著變；
        只有 QLabel 需要手動重上——它的顏色是建立當下寫死進 stylesheet 的。
        """
        self.title_lbl.setStyleSheet(f"color:{INK};background:transparent")
        if self.mode == "settings":
            self.sub_lbl.setStyleSheet(
                f"color:{C_ACCENT.name()};background:transparent")
        else:
            self.sub_lbl.setStyleSheet(f"color:{INK3};background:transparent")
        self.seg.update()

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
            cards = self.settings_page.cards
            # 每次進來都從頂端開始。停在上次離開的捲動位置，會讓人以為
            # 自己看到的是整頁——而最上面那幾項才是最常改的。
            self.pane.to_top()
        else:
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
            cards = self.page_cards[self.seg.index]

        # 壓暗 -> 換頁 -> 淡入。中間不能留給 Qt 任何一次重繪的機會，
        # 否則會先閃一幀全亮的新頁面。
        if animate:
            self._prime(cards)
        self.root.setCurrentIndex(0 if mode == "stats" else 1)
        self.cards = cards
        self._fit_height()
        self.update()
        if animate:
            self.play_cards()
        else:
            self._settle(cards)

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
        # 順序不能反：先把新頁面壓暗，再換過去。見 _prime()。
        cards = self.page_cards[i]
        self._prime(cards)
        self.stack.setCurrentIndex(i)
        self.cards = cards
        # 換頁重播進場：卡片依序滑入，讓人看見「這是一組新的東西」。
        # 用 play_cards 不是 play_in——視窗外框與標題沒有換，不該跟著閃。
        self.play_cards()

    # ------------------------------------------------------------ 動畫

    @staticmethod
    def _prime(cards):
        """把卡片壓到全透明。一定要在切換頁面之前做。

        QStackedWidget 換頁是立刻生效的，而新頁面的卡片還留著上次離開時的
        不透明度 1.0。先換頁再壓暗，中間就會被畫出一幀全亮的畫面——
        眼睛看到的是「亮一下 → 全黑 → 淡入」，那就是使用者說的閃。
        壓暗與換頁之間不能有任何一次重繪的機會。
        """
        for c in cards:
            c.sp.value = c.sp.velocity = c.sp.target = 0.0
            c.set_reveal(0.0)

    @staticmethod
    def _settle(cards):
        for c in cards:
            c.sp.snap(1.0)
            c.set_reveal(1.0)

    def play_in(self):
        """開窗：整個視窗淡入，然後卡片依序進場。"""
        self._closing = False
        self.sp_win.tune(*PRESET["enter"])
        self.sp_win.value = self.sp_win.velocity = 0.0
        self.sp_win.target = 1.0
        self.play_cards(start_delay=40)

    def play_cards(self, start_delay=0):
        """卡片重新進場，視窗本身不動。

        換頁不能重播 play_in()。那會把整個視窗的不透明度從 0 拉回 1，
        標題、外框、分頁控制項全部跟著閃一次——那不是換頁，看起來像視窗關掉重開。
        只有真正換掉的東西該動，沒換的東西動了就是在騙使用者說它變了。

        `start_delay` 只給開窗用：那時視窗自己也在淡入，卡片晚一點進來才有層次。
        換頁時必須是 0——頁面已經換掉了，還空著幾十毫秒不動，
        那段空白比動畫本身更顯眼。
        """
        for i, card in enumerate(self.cards):
            card.sp.value = card.sp.velocity = card.sp.target = 0.0
            card.set_reveal(0.0)
            delay = start_delay + i * STAGGER_MS
            if delay <= 0:
                card.sp.target = 1.0        # 第一張立刻開始，不排計時器
            else:
                QTimer.singleShot(delay, lambda c=card: self._start(c))
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
        Tip.hide_tip()
        self.sp_win.tune(*PRESET["exit"])
        self.sp_win.target = 0.0
        self._kick()

    def hideEvent(self, event):
        """視窗收起來，提示要跟著走。

        提示是獨立的頂層視窗，不是這個視窗的子元件，所以它不會自動被帶走
        ——留在螢幕上就是一塊擦不掉的字，而且底下的視窗已經不見了，
        使用者沒有任何辦法讓它消失。

        `Graphic.hideEvent` 那一條擋不到這個情況：Qt 只對「自己被隱藏」的元件
        送 Hide，父層被隱藏時子元件收到的是 HideToParent。所以要在這裡再接一次。
        """
        Tip.hide_tip()
        super().hideEvent(event)

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
        p.setPen(QPen(PAL.veil(28), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), 22, 22)

        hl = QLinearGradient(body.left(), body.top(), body.left(), body.top() + 80)
        hl.setColorAt(0.0, PAL.veil(30))
        hl.setColorAt(1.0, PAL.veil(0))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QBrush(hl), 1.0))
        p.drawRoundedRect(body.adjusted(1, 1, -1, -1), 21, 21)

        cx, cy = self.width() - SHADOW - WIN_PAD - 8, SHADOW + WIN_PAD + 14
        p.setPen(QPen(PAL.ink_a(214), 1.8, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPoint(cx - 7, cy - 7), QPoint(cx + 7, cy + 7))
        p.drawLine(QPoint(cx - 7, cy + 7), QPoint(cx + 7, cy - 7))

        # 齒輪（在設定頁時換成返回箭頭）。放在 × 左邊：關閉永遠在最外側，
        # 那是 Windows 的位置慣例，把它往內擠會讓人關錯。
        gx = cx - GEAR_GAP
        p.setPen(QPen(PAL.ink_a(214), 1.8, Qt.SolidLine, Qt.RoundCap,
                      Qt.RoundJoin))
        if self.mode == "settings":
            p.drawLine(QPoint(gx + 7, cy), QPoint(gx - 6, cy))
            p.drawLine(QPoint(gx - 6, cy), QPoint(gx - 1, cy - 5))
            p.drawLine(QPoint(gx - 6, cy), QPoint(gx - 1, cy + 5))
        else:
            self._draw_gear(p, gx, cy)
            # 有新版就在齒輪右上角點一顆。這是慣例（VS Code 的設定齒輪、
            # 瀏覽器的選單按鈕都是這樣做的）：有事就點一個點，沒事什麼都沒有。
            #
            # 畫在視窗外框上而不是塞一張卡進某一頁，所以它**不綁分頁**——
            # 今天／紀錄／成就切來切去它都在，而且不佔任何版面。
            #
            # 設定頁不畫：那時齒輪已經換成返回箭頭，而且使用者正看著底下
            # 那一列版本資訊，點在那裡沒有作用。
            if updates.checker.newer_release():
                dot = QPointF(gx + 6.5, cy - 6.5)
                # 先畫一圈底色再畫點。不墊的話點會跟齒輪的線條黏成一塊，
                # 看起來像齒輪長歪了而不是一個獨立的記號——徽章要讀成
                # 「疊在上面」，那一圈底色就是做這件事的。
                p.setPen(Qt.NoPen)
                p.setBrush(C_BG_TOP)
                p.drawEllipse(dot, 5.0, 5.0)
                p.setBrush(C_ACCENT)
                p.drawEllipse(dot, 3.4, 3.4)

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

    def resizeEvent(self, event):
        # popup 開著的時候視窗仍可能改高度（換頁、換主題）。不跟著長的話，
        # 遮罩會露出一條沒被蓋到的邊，而那條邊底下的東西是點得到的。
        super().resizeEvent(event)
        if self._confirm is not None and self._confirm.isVisible():
            self._confirm.setGeometry(0, 0, self.width(), self.height())

    def _ask_reset(self):
        """開確認的 popup。每次都重建：主題換過之後顏色是寫死在元件裡的，
        留著舊的會在淺色主題上出現一張深色的卡。
        """
        if self._confirm is not None:
            self._confirm.deleteLater()
        self._confirm = ConfirmOverlay(
            self, "清除所有紀錄？",
            "移除所有補水紀錄與連續天數，設定保留。此動作無法復原。")
        self._confirm.accepted.connect(self.settings_page._on_reset)
        self._confirm.ask()

    def keyPressEvent(self, event):
        # popup 開著的時候，Esc 是「關掉 popup」不是「關掉視窗」——
        # 一個鍵同時能取消確認又能關掉整個視窗，使用者按下去不知道會發生哪件事。
        if event.key() == Qt.Key_Escape:
            if self._confirm is not None and self._confirm.isVisible():
                self._confirm.dismiss()
                return
            self.close()


def open_window(cfg, events_path, existing=None, on_config=None,
                on_settings=False, on_replay=None):
    typeface.ensure_loaded()      # 只會做一次；讓渲染腳本單獨開視窗時也拿得到字體
    win = existing
    if win is None or not win.isVisible():
        win = StatsWindow(cfg, events_path, on_config=on_config,
                          on_replay=on_replay)
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

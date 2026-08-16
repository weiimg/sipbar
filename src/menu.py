# -*- coding: utf-8 -*-
"""系統匣與右鍵選單。

## 為什麼不用 QMenu

QMenu 在 Windows 上是原生的彈出視窗，樣式表改得動顏色與字，改不動圓角、
陰影與外框——它會在一片自繪的深色（或淺色）介面旁邊，開出一塊方角、
用系統字、跟其他東西完全不同語言的補丁。這跟先前把 QMessageBox 換掉是同一個理由。

這裡自己畫一個：同一套調色盤、同一個字體、同一組圓角與陰影、同樣的網格列高。

## Qt.Popup 負責的事

`Qt.Popup` 會替我們抓住滑鼠：點到外面、按 Esc、切換到別的視窗都會自動關閉。
自己做這件事要處理焦點、多螢幕、以及「點到自己」的例外，很容易留下一個
關不掉的浮動視窗。
"""

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen,
)
from PySide6.QtWidgets import QApplication, QWidget

import theme
import typeface
from paintkit import draw_soft_shadow, shadow_alphas

GRID = 8
ROW_H = GRID * 5           # 40：選單列。有東西可點，要留得下點擊區
HEAD_H = GRID * 6          # 48：頂端那行狀態，兩行文字
SEP_H = GRID + 1           # 分隔線連同上下留白
PAD_V = GRID               # 內容上下內距
PAD_H = GRID * 2           # 內容左右內距
WIDTH = 268
RADIUS = 14
SHADOW = 22
SHADOW_SIGMA = 8.0
SHADOW_OFFSET_Y = 5


class TrayMenu(QWidget):
    """自繪的彈出選單。

    項目用 (文字, 回呼) 表示；回呼是 None 就是分隔線。
    第一列是狀態，不可點。
    """

    closed = Signal()

    def __init__(self, head, items):
        super().__init__()
        self.pal = theme.active()
        self.head = head                      # (主字, 副字)
        # (label, callback, muted)。label 為 None 就是分隔線。
        # muted 給「結束程式」這種跟其他項目不同類、但還不到危險程度的動作。
        self.items = [it if len(it) == 3 else (it[0], it[1], False) for it in items]
        self.hover = -1

        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint |
                            Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self._f_head = typeface.make(16, QFont.Bold)
        self._f_sub = typeface.make(14, QFont.Medium)
        self._f_item = typeface.make(16, QFont.Medium)
        self._alphas = shadow_alphas(SHADOW - 2, self.pal.shadow_peak * 1.2,
                                     SHADOW_SIGMA)

        self._rows = []                       # (y, h, index)，index=-1 代表不可點
        y = PAD_V + HEAD_H + SEP_H
        for i, (label, cb, _muted) in enumerate(self.items):
            if label is None:
                y += SEP_H
                continue
            self._rows.append((y, ROW_H, i))
            y += ROW_H
        self._content_h = y + PAD_V
        self.resize(WIDTH + SHADOW * 2, self._content_h + SHADOW * 2)

    # ------------------------------------------------------------ 版面

    def _body(self):
        return QRectF(SHADOW, SHADOW, WIDTH, self._content_h)

    def _row_at(self, pos):
        x = pos.x() - SHADOW
        if not (0 <= x <= WIDTH):
            return -1
        y = pos.y() - SHADOW
        for top, h, idx in self._rows:
            if top <= y < top + h:
                return idx
        return -1

    # ------------------------------------------------------------ 互動

    def popup_at(self, global_pos):
        """在游標附近彈出，並確保整個選單留在螢幕內。

        Windows 的系統匣在右下角，選單若照游標直接往右下展開會被切掉，
        所以往左上翻。這是原生選單自動做、自繪就得自己做的事。
        """
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        x, y = global_pos.x() - SHADOW, global_pos.y() - SHADOW
        if x + self.width() > area.right():
            x = global_pos.x() - self.width() + SHADOW
        if y + self.height() > area.bottom():
            y = global_pos.y() - self.height() + SHADOW
        x = max(area.left(), min(x, area.right() - self.width()))
        y = max(area.top(), min(y, area.bottom() - self.height()))
        self.move(int(x), int(y))
        self.show()

    def mouseMoveEvent(self, event):
        idx = self._row_at(event.position())
        if idx != self.hover:
            self.hover = idx
            self.update()

    def leaveEvent(self, event):
        self.hover = -1
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        idx = self._row_at(event.position())
        self.close()
        if idx >= 0 and self.items[idx][1]:
            self.items[idx][1]()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    # ------------------------------------------------------------ 繪製

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        pal = self.pal
        body = self._body()

        draw_soft_shadow(p, body, self._alphas, offset_y=SHADOW_OFFSET_Y,
                         corner=RADIUS)

        g = QLinearGradient(body.left(), body.top(), body.left(), body.bottom())
        g.setColorAt(0.0, QColor(pal.bg_top))
        g.setColorAt(1.0, QColor(pal.bg_bottom))
        p.setPen(QPen(pal.veil(28), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)

        left = SHADOW + PAD_H
        right = SHADOW + WIDTH - PAD_H

        # 頂端狀態：主字一行、副字一行。不可點，所以不給 hover。
        #
        # 兩行都先過省略號。**文字永遠不該有機會跑出容器**——即使呼叫端已經
        # 盡量寫短，狀態字串是動態組出來的（連續天數破百、暫停到某個時刻…），
        # 總有一天會超過。省略號是最後一道防線，不是備案。
        head_y = SHADOW + PAD_V
        avail = right - left
        fm = QFontMetrics(self._f_head)
        p.setFont(self._f_head)
        p.setPen(pal.ink_a(255))
        p.drawText(left, int(head_y + fm.ascent() + 2),
                   fm.elidedText(self.head[0], Qt.ElideRight, avail))
        if self.head[1]:
            fs = QFontMetrics(self._f_sub)
            p.setFont(self._f_sub)
            p.setPen(pal.ink_a(150))
            p.drawText(left, int(head_y + HEAD_H - fs.descent() - 2),
                       fs.elidedText(self.head[1], Qt.ElideRight, avail))

        sep_y = head_y + HEAD_H + SEP_H // 2
        p.fillRect(int(left), int(sep_y), int(right - left), 1, pal.veil(20))

        fi = QFontMetrics(self._f_item)
        baseline = (fi.ascent() - fi.descent()) / 2
        for top, h, idx in self._rows:
            label, cb, muted = self.items[idx]
            y = SHADOW + top
            if idx == self.hover:
                p.setPen(Qt.NoPen)
                p.setBrush(pal.veil(26))
                p.drawRoundedRect(QRectF(left - GRID, y + 2,
                                         right - left + GRID * 2, h - 4), 9, 9)
            p.setFont(self._f_item)
            # muted 的項目降一階顏色：它跟其他項目不是同一類動作，
            # 但也還不到危險的程度——降一階就夠把它從主要動作裡分出來。
            p.setPen(pal.ink_a(160 if muted else 255))
            p.drawText(int(left), int(y + h / 2 + baseline),
                       fi.elidedText(label, Qt.ElideRight, avail))

        # 分隔線畫在被標記為分隔的位置之前
        for i, (label, cb, _m) in enumerate(self.items):
            if label is None:
                prev = [r for r in self._rows if r[2] < i]
                if prev:
                    ly = SHADOW + prev[-1][0] + prev[-1][1] + SEP_H // 2
                    p.fillRect(int(left), int(ly), int(right - left), 1,
                               pal.veil(20))

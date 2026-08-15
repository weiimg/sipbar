# -*- coding: utf-8 -*-
"""首次啟動的引導。

## 為什麼只問一件事

規劃文件當初列了四題（水壺、體重、幾點睡、螢幕），但那是程式還不會自己推導時
寫的。現在目標有預設、起床時間會從活動紀錄推、單螢幕根本不顯示螢幕選項——
**第一天問得到、而且問了會改變成敗的，只剩「桌上有沒有水」，而那根本不是設定，
是一個行為介入。**

規劃文件裡最重的一句：

> 先在桌上放一個大水壺，這個工具才有意義。工具解決不了物流問題。
> 這是整個計畫成敗最大的單一因素，而它跟寫程式無關。

所以那一題單獨占一頁。跟體重並排會讓它讀起來像同一類東西，它不是——
它是唯一一個答錯會讓整個工具失效的問題。

答「還沒有」會多出一頁請他去裝水，**但不擋**：文案已經把話說清楚，
第一次用就被鎖住只會讓人直接關掉程式。

## 為什麼要演一次動畫

這個工具最大的可發現性問題是它平常完全隱藏。文字寫「時間到才從螢幕頂端滑下來」，
讀的人得自己想像那是什麼樣子；演一次就不用想像。
預覽用的是跟本體同一套彈簧物理，所以引導裡的手感跟實際看到的一致。
"""

import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QBrush, QColor, QDesktopServices, QFontMetrics, QLinearGradient, QPainter,
    QPen, QPolygonF,
)
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

import pixelface
import settings as appsettings
import stats_window as sw
import typeface
from motion import PRESET, Spring, clamp, ease, lerp
from paintkit import draw_soft_shadow, shadow_alphas

WIDTH = 560                 # 比紀錄視窗窄：引導一次只講一件事

# 彩蛋：回答「還沒有」時，用預設瀏覽器播巧虎的喝水歌。
# 這是整個引導唯一一個會離開程式的動作，也是唯一會用到網路的地方——
# 「關於」那頁的隱私聲明因此不能寫「本程式無網路連線」，
# 要寫成「不蒐集也不傳送任何資料」，那句才是真的。
WATER_SONG_URL = "https://youtu.be/P5YaZlGD1lI"

# ---------------------------------------------------------------- 文案
#
# 語氣參考 Finch（自我照顧鳥）：**溫柔、把事情拆小、講分工。**
# 它常被當成「反 Duolingo」的範例——同樣是養一隻角色，但那隻鳥從不責備，
# 只把該做的事拆到小得像順手，然後謝謝你。可愛來自體貼，不來自賣萌。
#
# ## 這一版沒有結構性的保障，所以規則要寫死
#
# 上一版走任天堂 CF 的路，用第三人稱描述那隻杯子（「它沒有手」）。那個寫法
# 有個附帶好處：**不開口的角色沒辦法情勒**，這條路從結構上就封住了。
# Finch 是第一人稱，那個保障就沒了。所以規則必須明講：
#
# **角色可以有情緒，但情緒不能當條件。**
#
# - 可以：「時間我來記，你只要伸手」（分工）
# - 可以：「我在這裡等」（陪伴）
# - 不行：「我不怪你，但我也不會閉嘴」（把「我不會停」當籌碼）
# - 不行：任何形式的「你不做，我就會怎樣」
#
# 島自己的台詞不受這條管（「還在等」「撐不太住」正是角色在示弱，那是設計核心）。
# **差別在於：島是在事件發生的當下反應，引導是在使用者還沒開始前就先預設立場。**
#
# ## 走過的路
#
# - 初版是設計文件的句法（「這個工具唯一解決不了的問題是…忽略它是合理的選擇」），
#   先講抽象命題、再用被動語態下結論。第一次打開程式的人不是來讀論證的。
# - 第二版學 Duolingo，寫成「我不怪你，但我也不會閉嘴」。威脅包成體諒。
# - 第三版學任天堂 CF，平述句加第三人稱。乾淨，但冷。
#
# 底線始終不變：講的每件事都要是真的產品行為。「沒有關閉按鈕」是設計決定，
# 「走去廚房那段路我幫不上忙」是它真的做不到的事。
#
# 按鈕與開關的標籤不在這個範圍內，那些仍然是標籤，仍然受 test_copy_style.py 管。
# copy-style: off
WATER_LEAD = ("這裡只需要你先準備一件事：水放到手邊。"
              "走去廚房那段路我幫不上忙，但只要水在手邊，剩下的時間我來記。")
FILL_LEAD = "去吧，我在這裡等。其他都不用設定。"
# 彩蛋真的開起來了才這樣寫。開失敗還說「配了首歌」就是介面在說謊。
FILL_LEAD_SONG = "去吧，我在這裡等，順便配了首歌。其他都不用設定。"
HOW_BULLETS = ("平常我不佔位置，時間到才從螢幕上緣滑下來",
               "點我一下就算喝了，點系統匣的圖示也一樣",
               "沒有關閉按鈕，喝完我自己會退回去")
HOW_SETTINGS = "覺得太密或太少，設定裡都能調。入口在系統匣圖示的選單，或紀錄視窗右上角的齒輪。"
# copy-style: on

PAD = 32
SHADOW = 30
SHADOW_SIGMA = 11.0
SHADOW_OFFSET_Y = 7
RADIUS = 22
CHROME = (SHADOW + PAD) * 2     # 內容以外的上下留白，視窗高度 = 內容 + 這個


class Button(sw.Graphic):
    """主要動作用實心藥丸，次要動作用文字。"""

    clicked = Signal()

    def __init__(self, text, primary=True):
        f = sw.font("headline" if primary else "body")
        super().__init__(QFontMetrics(f).horizontalAdvance(text) + 56,
                         44 if primary else 30)
        self.text, self.primary, self._f = text, primary, f
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setOpacity(clamp(ease(self.reveal), 0.0, 1.0))
        fm = QFontMetrics(self._f)
        p.setFont(self._f)
        if self.primary:
            p.setPen(Qt.NoPen)
            p.setBrush(sw.C_ACCENT)
            p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()),
                              self.height() / 2, self.height() / 2)
            p.setPen(QColor(255, 255, 255, 245))
        else:
            p.setPen(sw.PAL.ink_a(170))
        p.drawText(int((self.width() - fm.horizontalAdvance(self.text)) / 2),
                   int(self.height() / 2 + (fm.ascent() - fm.descent()) / 2),
                   self.text)


class IslandPreview(sw.Graphic):
    """縮小版的動態島，循環演一遍它會怎麼出現。

    循環：藏在螢幕上緣後面 -> 滑下來展開 -> 游標點一下 -> 變成已記錄 -> 滑回去。
    """

    # 高度只留藥丸滑到底所需的：上緣線在 26，藥丸滑完底部在 74，再留 14 收邊。
    # 初版給了 120，下面 46px 永遠是空的——那段空白會被讀成「預覽跟條列之間的
    # 分隔」，條列就飄成另一個區塊了。
    W, H = 464, 88
    SCREEN_TOP = 26            # 那條代表螢幕上緣的線
    PILL_MIN_W, PILL_MAX_W = 84, 248
    PILL_H = 34
    # 死時間要少。初版 4.2 秒的循環有 1.7 秒是空的，看起來像壞掉。
    T_APPEAR, T_POINT, T_CLICK, T_LEAVE, T_LOOP = 0.3, 1.2, 1.9, 2.6, 3.4

    def __init__(self):
        super().__init__(self.W, self.H)
        self.t = 0.0
        self.sp_drop = Spring(0.0, *PRESET["reveal"])
        self.sp_open = Spring(0.0, *PRESET["expand"])
        self.phase = "hidden"
        self._f = sw.font("caption")
        self._last = time.perf_counter()
        self.frame = QTimer(self)
        self.frame.setInterval(16)
        self.frame.timeout.connect(self._tick)

    def start(self):
        self._last = time.perf_counter()
        self.frame.start()

    def stop(self):
        self.frame.stop()

    def _tick(self):
        now = time.perf_counter()
        self.step(now - self._last)
        self._last = now

    def step(self, dt):
        self.t = (self.t + dt) % self.T_LOOP
        t = self.t
        if t < self.T_APPEAR:
            self.phase = "hidden"
            self.sp_drop.target = self.sp_open.target = 0.0
        elif t < self.T_POINT:
            self.phase = "thirsty"
            self.sp_drop.target = self.sp_open.target = 1.0
        elif t < self.T_CLICK:
            self.phase = "pointing"
        elif t < self.T_LEAVE:
            self.phase = "done"
        else:
            self.phase = "leaving"
            self.sp_drop.target = self.sp_open.target = 0.0
        self.sp_drop.step(dt)
        self.sp_open.step(dt)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setOpacity(clamp(ease(self.reveal), 0.0, 1.0))

        # 一條線代表螢幕上緣。畫成方塊的話讀起來像個容器，
        # 沒有人會把它理解成「螢幕的邊」。
        top = self.SCREEN_TOP
        p.setPen(QPen(sw.PAL.veil(34), 1))
        p.drawLine(0, top, self.W, top)
        p.setFont(self._f)
        p.setPen(sw.PAL.ink_a(110))
        p.drawText(2, top - 6, "螢幕上緣")

        drop = clamp(self.sp_drop.value, 0.0, 1.0)
        if drop < 0.01:
            return

        openness = clamp(self.sp_open.value, 0.0, 1.2)
        w = lerp(self.PILL_MIN_W, self.PILL_MAX_W, clamp(openness, 0.0, 1.0))
        y = top - self.PILL_H + drop * (self.PILL_H + 14)
        pill = QRectF((self.W - w) / 2, y, w, self.PILL_H)

        pg = QLinearGradient(pill.left(), pill.top(), pill.left(), pill.bottom())
        pg.setColorAt(0.0, QColor(30, 31, 36, 246))
        pg.setColorAt(1.0, QColor(14, 15, 18, 246))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(pg))
        p.drawRoundedRect(pill, self.PILL_H / 2, self.PILL_H / 2)

        done = self.phase == "done"
        pixelface.draw_cup(p, int(pill.left() + 20), int(pill.center().y()),
                           1.0 if done else 0.22,
                           "SATISFIED" if done else "THIRSTY", pixelface.GLASS,
                           pixelface.WATER_DONE if done else pixelface.WATER,
                           pixelface.INK, cell=2)

        if openness > 0.35:
            fm = QFontMetrics(self._f)
            p.setFont(self._f)
            base = p.opacity()
            p.setOpacity(base * clamp((openness - 0.35) / 0.4, 0.0, 1.0))
            p.setPen(QColor(245, 245, 247))
            p.drawText(int(pill.left() + 38),
                       int(pill.center().y() + (fm.ascent() - fm.descent()) / 2),
                       "已記錄" if done else "該喝水了")
            p.setOpacity(base)

        if self.phase in ("pointing", "done"):
            self._draw_cursor(p, pill, self.phase == "done")

    @staticmethod
    def _draw_cursor(p, pill, hit):
        # 尖端要落在藥丸**上面**，不是旁邊：指錯地方的指引比沒有指引更糟。
        pt = QPointF(pill.right() - 34, pill.center().y() + 2)
        if hit:
            p.setPen(QPen(sw.C_ACCENT, 2))
            p.setBrush(Qt.NoBrush)
            r = 15
            p.drawEllipse(QRectF(pt.x() - r, pt.y() - r, r * 2, r * 2))
        # 白底黑框，跟作業系統的游標同一套做法。游標會同時壓在深色藥丸與
        # 淺色背景上，單一顏色一定會在其中一邊消失。
        p.setPen(QPen(QColor(20, 20, 22, 235), 1.4, Qt.SolidLine, Qt.RoundCap,
                      Qt.RoundJoin))
        p.setBrush(QBrush(QColor(255, 255, 255, 245)))
        p.drawPolygon(QPolygonF([
            QPointF(pt.x(), pt.y()), QPointF(pt.x(), pt.y() + 15),
            QPointF(pt.x() + 4, pt.y() + 11.5), QPointF(pt.x() + 7, pt.y() + 17),
            QPointF(pt.x() + 9.5, pt.y() + 16), QPointF(pt.x() + 6.5, pt.y() + 10.5),
            QPointF(pt.x() + 11, pt.y() + 10)]))


def _bullet(text):
    return sw.row(sw.Label("・", "body", sw.INK3), (sw.para(text), 1),
                  spacing=sw.S1)


def page_height(page):
    """問版面引擎這一頁要多高，不要自己加總。

    `sizeHint` 與 `minimumSize` 取大的那個：會換行的 QLabel 兩者不一定相等
    （實測「開始之前」是 223 / 223，但 heightForWidth 只要 201），取小的會被
    版面引擎當成壓縮，文字就疊在一起。多出來的幾 px 留白看不出來，壓扁看得出來。
    """
    lay = page.layout()
    lay.activate()
    return max(lay.sizeHint().height(), lay.minimumSize().height())


class Deck(QWidget):
    """換頁容器：每頁維持自己的自然高度，容器高度由外面的彈簧補間，超出的裁掉。

    **不能用 QStackedWidget。** 它的高度是所有頁面的最大值，短的那幾頁底下就空一片
    （實測三頁自然高度 223 / 181 / 597，第二頁有七成是空的，讀起來像沒做完）。
    而且它會把當前頁拉成跟自己一樣高，長高的過程中頁面會先被壓扁——
    IslandPreview 是固定尺寸，壓下去就是切掉。

    改成頁面保持自然高度、由容器裁切之後，長高變成「內容從上往下露出來」，
    那正好是引導往前走的方向；縮短則是下面的空白收起來。兩邊都不會壓到內容。
    """

    def __init__(self, width):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._w = width
        self.pages = []
        self.index = 0

    def add(self, page):
        page.setParent(self)
        page.setFixedWidth(self._w)
        page.setGeometry(0, 0, self._w, page_height(page))
        page.setVisible(not self.pages)      # 只有第一頁一開始是開的
        self.pages.append(page)

    def show_page(self, index):
        for i, page in enumerate(self.pages):
            page.setVisible(i == index)
        self.index = index

    def natural(self, index=None):
        return self.pages[self.index if index is None else index].height()

    def remeasure(self, index):
        """換過那一頁的文字之後重量高度。高度是 add() 當下量的，不重量會裁掉。"""
        page = self.pages[index]
        page.setGeometry(0, 0, self._w, page_height(page))


class OnboardWindow(QWidget):
    """三頁引導。第二頁只在回答「還沒有」時出現。"""

    finished = Signal(bool)          # 參數：開機時啟動要不要開

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("喝水提醒動態島")
        self._drag = None

        self.preview = IslandPreview()
        self.autostart = sw.Toggle(True)

        # 視窗自己排幾何，不掛 layout。掛了的話 Deck 的高度變化會回頭去改視窗的
        # 最小／最大高度，跟這裡逐格設定的高度打架，動畫會抖。
        self.deck = Deck(WIDTH - PAD * 2)
        self.deck.setParent(self)
        for page in (self._page_water(), self._page_fill(), self._page_howto()):
            self.deck.add(page)

        self.sp_win = Spring(0.0, *PRESET["enter"])
        # 高度走 0..1 的補間而不是直接放像素：Spring.settled 的門檻是為 0..1
        # 設計的，放幾百的像素值永遠不會判定為停下來。
        self.sp_h = Spring(1.0, *PRESET["content"])
        self._h_from = self._h_to = self.deck.natural(0)
        self._anchor_y = 0
        self.setWindowOpacity(0.0)
        self._last = time.perf_counter()
        self.frame = QTimer(self)
        self.frame.setInterval(16)
        self.frame.timeout.connect(self._step)

        self._alphas = shadow_alphas(SHADOW - 2, sw.PAL.shadow_peak, SHADOW_SIGMA)
        self.resize(WIDTH + SHADOW * 2, self._h_to + CHROME)

    # ------------------------------------------------------------ 頁面

    def _page(self, title, blocks, actions):
        page = QWidget()
        page.setAttribute(Qt.WA_TranslucentBackground)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(sw.S3)
        lay.addWidget(sw.Label(title, "title", sw.INK))
        for b in blocks:
            lay.addWidget(b)
        # 動作靠右下，跟內容之間空兩格。頁面現在是自然高度，沒有多餘空間可以
        # 把按鈕推遠，距離要自己給——貼著內文的按鈕會被讀成內文的一部分。
        lay.addSpacing(sw.S3)
        lay.addWidget(sw.row("stretch", *actions, spacing=sw.S3))
        return page

    def _page_water(self):
        yes = Button("有，繼續")
        no = Button("還沒有", primary=False)
        yes.clicked.connect(lambda: self._go(2))
        no.clicked.connect(self._no_water)
        return self._page("開始之前", [
            sw.para(WATER_LEAD),
            sw.Label("桌上現在有水嗎？", "headline", sw.INK),
        ], [no, yes])

    def _no_water(self):
        """彩蛋：回答「還沒有」就用瀏覽器播喝水歌，邊裝邊聽。

        開不起來也不影響流程——沒有歌就沒有歌，引導照樣往下走。
        （這個專案有過一次教訓：把成敗押在作業系統的檔案關聯上，
        `webbrowser.open()` 靜默失敗、什麼都沒發生也查不出來。
        QDesktopServices 走的是預設瀏覽器而不是副檔名關聯，
        但一樣包起來，不讓它有機會把引導打斷。）
        """
        played = False
        try:
            played = QDesktopServices.openUrl(QUrl(WATER_SONG_URL))
        except Exception:
            played = False
        self.fill_lead.setText(FILL_LEAD_SONG if played else FILL_LEAD)
        # 換過字才量高度。兩句都只有一行，但那是現在——文案一改就可能變兩行，
        # 而頁面的高度是在 Deck.add() 時量的，不重量就會裁掉最後一行。
        self.deck.remeasure(1)
        self._go(1)

    def _page_fill(self):
        # 不擋：按鈕隨時可以按。文案已經把話講清楚，第一次用就被鎖住
        # 只會讓人直接關掉程式。
        ok = Button("裝好了")
        ok.clicked.connect(lambda: self._go(2))
        self.fill_lead = sw.para(FILL_LEAD)
        return self._page("先去裝一壺", [self.fill_lead], [ok])

    def _page_howto(self):
        start = Button("開始")
        start.clicked.connect(self._finish)
        return self._page("這樣用", [
            self.preview,
            # 三條是同一組，行距要比它們跟上下文的距離短。用頁面的 S3 排會讓
            # 三條各自讀成一段，掃過去像三件無關的事。
            sw.col(*[_bullet(t) for t in HOW_BULLETS], spacing=sw.S2),
            sw.Divider(),
            # 把「在哪裡」也寫出來。這個程式平常完全隱藏，
            # 使用者不會自己想到齒輪在紀錄視窗右上角。
            sw.para(HOW_SETTINGS),
            sw.setting_row("開機時啟動", self.autostart),
        ], [start])

    # ------------------------------------------------------------ 流程

    def _go(self, index):
        if index == self.deck.index:
            return
        self.deck.show_page(index)
        if index == 2:
            self.preview.start()
        # 中心線鎖在切換的那一刻。高度往兩邊長，視窗才不會愈走愈往下、
        # 到第三頁時掉出螢幕（實測 1080p 上會少 8px）。
        self._anchor_y = self.y() + self.height() / 2
        self._h_from = self.height() - CHROME
        self._h_to = self.deck.natural()
        self.sp_h.value = self.sp_h.velocity = 0.0
        self.sp_h.target = 1.0
        self._last = time.perf_counter()
        self.frame.start()

    def _apply_height(self):
        h = int(round(lerp(self._h_from, self._h_to,
                           clamp(self.sp_h.value, 0.0, 1.0)))) + CHROME
        if h == self.height():
            return
        scr = QApplication.primaryScreen().availableGeometry()
        top = int(self._anchor_y - h / 2)
        top = max(scr.top() + 20, min(top, scr.bottom() - h - 20))
        # 一次 setGeometry，不要 resize 完再 move：兩次視窗操作在 Windows 上
        # 是兩次合成，會看到框先變高再跳位。
        self.setGeometry(self.x(), top, self.width(), h)

    def _finish(self):
        self.preview.stop()
        self.finished.emit(self.autostart.on)
        self.close()

    # ------------------------------------------------------------ 外觀

    def anchor_here(self):
        """把目前的垂直中心記成基準。移動視窗之後要叫一次。"""
        self._anchor_y = self.y() + self.height() / 2

    def play_in(self):
        self.sp_win.value = self.sp_win.velocity = 0.0
        self.sp_win.target = 1.0
        self._last = time.perf_counter()
        self.frame.start()

    def _step(self):
        now = time.perf_counter()
        dt = now - self._last
        self._last = now
        self.sp_win.step(dt)
        self.setWindowOpacity(clamp(self.sp_win.value, 0.0, 1.0))
        self.sp_h.step(dt)
        self._apply_height()
        if self.sp_win.settled and self.sp_h.settled:
            self.sp_win.snap()
            self.sp_h.snap()
            self.setWindowOpacity(1.0)
            self._apply_height()
            self.frame.stop()

    def resizeEvent(self, event):
        self.deck.setGeometry(SHADOW + PAD, SHADOW + PAD,
                              WIDTH - PAD * 2, self.height() - CHROME)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        body = QRectF(SHADOW, SHADOW, self.width() - SHADOW * 2,
                      self.height() - SHADOW * 2)
        draw_soft_shadow(p, body, self._alphas, offset_y=SHADOW_OFFSET_Y,
                         corner=RADIUS)
        g = QLinearGradient(body.left(), body.top(), body.left(), body.bottom())
        g.setColorAt(0.0, sw.C_BG_TOP)
        g.setColorAt(1.0, sw.C_BG_BOTTOM)
        p.setPen(QPen(sw.PAL.veil(28), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(body.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, event):
        if self._drag:
            self.anchor_here()      # 拖過之後，下一頁要以新位置為中心長高
        self._drag = None


def open_window(on_finished):
    """開引導視窗。回傳視窗物件，呼叫端要留參考否則會被回收。"""
    typeface.ensure_loaded()
    win = OnboardWindow()
    win.finished.connect(on_finished)
    screen = QApplication.primaryScreen().availableGeometry()
    # 對齊螢幕中心，不是對齊第一頁的中心：後面兩頁高度不同，鎖住中心線
    # 才不會走到第三頁時整個視窗偏一邊。
    win.move(screen.center().x() - win.width() // 2,
             max(screen.top() + 40, screen.center().y() - win.height() // 2))
    win.anchor_here()
    win.show()
    win.play_in()
    return win

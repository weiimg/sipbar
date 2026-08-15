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

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QBrush, QColor, QDesktopServices, QFontMetrics, QImage, QLinearGradient,
    QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
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
# ## 借態度，不要借句型
#
# 第一版照著 Finch 的英文句構寫，得到的是翻譯腔：「這裡只需要你先準備一件事」
# 「走去廚房那段路我幫不上忙」。意思對、溫度也對，但**中文不會這樣講話**。
#
# 台灣人講同一件事會用「幫你」「交給我」「在這等你」這種說法：動詞前面掛一個
# 對象，把分工講成人跟人之間的事，而不是條件與範圍的宣告。
#
# **參考國外產品的時候，借的是它對使用者的態度，不是它的句子結構。**
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
# 驚嘆號**只放在承諾與送行**，不放在說明。「時間就交給我！」是它接下這件事，
# 「我在這等你！」是送你出門，兩個都是有情緒的時刻。第三頁的條列是說明書，
# 加了驚嘆號就變成廣告。**全部都有等於全部都沒有。**
WATER_LEAD = ("你只要先做一件事：把水放在手邊。"
              "要走去廚房的話我幫不上忙，但水在旁邊，時間就交給我！")
FILL_LEAD = "先去裝，我在這等你！其他都不用設定。"
# 彩蛋真的開起來了才這樣寫。開失敗還說「配了首歌」就是介面在說謊。
FILL_LEAD_SONG = "先去裝，我在這等你，順便配了首歌！其他都不用設定。"
HOW_BULLETS = ("平常我不會出現，時間到才從螢幕上緣滑下來",
               "點我一下就算喝了，點系統匣的圖示也可以",
               "沒有關閉按鈕，喝完我就自己回去了")
HOW_SETTINGS = "覺得太吵或不夠，設定裡都可以改。從系統匣圖示的選單，或紀錄視窗右上角的齒輪進去。"
# 第四頁：真的點一次。**「這次不算」一定要寫出來**——不寫的話，
# 一個在意數字的人會猶豫要不要點，而這一步的全部目的就是讓他點下去。
TRY_LEAD = "點我一下試試。這次不會算進今天的次數。"
TRY_DONE = "就是這樣。之後時間到我會自己出現。"
# 它自己的名字。**維持白話的叫法**，不另外取一個。這個工具全篇都不用內部術語，
# 角色也一樣：使用者看到的是一隻杯子，那它就叫杯子。
NAME = "杯子"
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
    """一台縮小的電腦桌面，循環演一遍動態島會怎麼出現。

    循環：藏在螢幕上緣外面 -> 滑下來展開 -> 游標點一下 -> 變成已記錄 -> 滑回去。

    ## 為什麼要畫整台桌面

    初版只畫一條線代表螢幕上緣，旁邊標一行小字「螢幕上緣」。那是**用文字解釋
    一張圖**——需要旁白的示意圖等於沒說清楚，而且那行小字比它要解釋的東西還難懂。

    改成畫一台有桌布、有工作列的縮小螢幕，藥丸從它的上緣滑進來，還被螢幕邊界
    裁掉一半。不用任何文字，位置關係自己講完了。

    ## 藥丸的尺寸是刻意誇張的

    照實際比例，動態島在 3440px 的螢幕上只佔 4%（收合）到 12.5%（展開）。
    縮到這張圖上就是 15px 寬，杯子的臉根本畫不出來。
    **這是示意圖不是比例尺**，所以放大到看得見表情為止；讀的人要拿到的資訊是
    「它從上面中間出現、點一下就走」，不是「它有多大」。
    """

    W, H = 464, 150
    BEZEL = 8                  # 螢幕外框的厚度
    FADE_H = 62                # 下緣羽化掉的高度
    PILL_MIN_W, PILL_MAX_W = 42, 110
    PILL_H = 30
    CUP_CELL = 2
    DOTS = 7                   # 進度點，跟島上的一樣
    DOT_D, DOT_GAP = 5, 4
    DOTS_BEFORE, DOTS_AFTER = 3, 4      # 點一下就多一格
    # 死時間要少。初版 4.2 秒的循環有 1.7 秒是空的，看起來像壞掉。
    T_APPEAR, T_POINT, T_CLICK, T_LEAVE, T_LOOP = 0.3, 1.2, 1.9, 2.6, 3.4

    tapped = Signal()

    def __init__(self, interactive=False):
        super().__init__(self.W, self.H)
        self.t = 0.0
        self.sp_drop = Spring(0.0, *PRESET["reveal"])
        self.sp_open = Spring(0.0, *PRESET["expand"])
        self.phase = "hidden"
        self._wall = None      # 桌布只畫一次，見 _build_wallpaper
        self._f = sw.font("caption")
        # 互動模式：不循環，滑下來就停著等人點。**點下去不會記任何東西**——
        # 這裡畫的是一張圖，跟島與 events.jsonl 沒有任何連線，
        # 所以「這次不算今天的次數」不是靠寫程式擋，是它本來就碰不到。
        self.interactive = interactive
        self.tapped_once = False
        self._tap_t = 0.0
        self._pill = QRectF()          # 最後畫出來的位置，給命中測試用
        if interactive:
            self.setCursor(Qt.PointingHandCursor)
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

    def mousePressEvent(self, event):
        if (self.interactive and not self.tapped_once
                and event.button() == Qt.LeftButton
                and self._pill.contains(event.position())):
            self.tapped_once = True
            self._tap_t = self.t
            self.tapped.emit()

    def step(self, dt):
        if self.interactive:
            return self._step_interactive(dt)
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

    def _step_interactive(self, dt):
        """滑下來就停著等人點，點完才走。不循環。

        **不畫假游標。** 循環展示時那隻假游標是在演給人看；這裡使用者自己的
        游標就在畫面上，再畫一隻只會讓人分不清該動哪一隻。
        改成藥丸外圈一道會呼吸的光暈，那是「可以點」而不是「我在點」。
        """
        self.t += dt
        if not self.tapped_once:
            waiting = self.t >= 0.4
            self.phase = "waiting" if waiting else "hidden"
            self.sp_drop.target = self.sp_open.target = 1.0 if waiting else 0.0
        else:
            since = self.t - self._tap_t
            if since < 1.5:
                self.phase = "done"
            else:
                self.phase = "leaving"
                self.sp_drop.target = self.sp_open.target = 0.0
        self.sp_drop.step(dt)
        self.sp_open.step(dt)
        self.update()

    def paintEvent(self, event):
        # **先畫進一張帶透明度的圖層，最後再把下緣羽化掉。**
        # 直接畫在 widget 上做不到：要淡出的是「螢幕外框＋桌布＋藥丸」整組東西，
        # 那需要對已經畫好的像素做 alpha 運算，不是疊一層漸層色上去
        # （疊色會變成「蓋一片卡片色」，換主題或換底色就穿幫）。
        layer = QImage(self.W, self.H, QImage.Format_ARGB32_Premultiplied)
        layer.fill(Qt.transparent)
        lp = QPainter(layer)
        lp.setRenderHint(QPainter.Antialiasing, True)

        screen = self._draw_screen(lp)
        drop = clamp(self.sp_drop.value, 0.0, 1.0)
        if drop >= 0.01:
            # **藥丸要被螢幕邊界裁掉**。它是從螢幕外面滑進來的，不裁的話會浮在
            # 螢幕上方，那正好是要說明的位置關係裡最關鍵的一段。
            lp.save()
            lp.setClipRect(screen)
            self._draw_pill(lp, screen)
            lp.restore()

        fade = QLinearGradient(0, self.H - self.FADE_H, 0, self.H)
        fade.setColorAt(0.0, QColor(0, 0, 0, 255))
        fade.setColorAt(1.0, QColor(0, 0, 0, 0))
        lp.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        lp.fillRect(QRectF(0, self.H - self.FADE_H, self.W, self.FADE_H),
                    QBrush(fade))
        lp.end()

        p = QPainter(self)
        p.setOpacity(clamp(ease(self.reveal), 0.0, 1.0))
        p.drawImage(0, 0, layer)

    def _draw_pill(self, p, screen):
        openness = clamp(self.sp_open.value, 0.0, 1.2)
        w = lerp(self.PILL_MIN_W, self.PILL_MAX_W, clamp(openness, 0.0, 1.0))
        drop = clamp(self.sp_drop.value, 0.0, 1.0)
        # 互動時停低一點：呼吸光暈往外長 12px，停在原本的位置會整圈被螢幕上緣
        # 裁掉，看起來就只是一顆普通藥丸，「可以點」那個訊號整個消失。
        settle = 26 if self.interactive else 12
        y = screen.top() - self.PILL_H + drop * (self.PILL_H + settle)
        pill = QRectF(screen.center().x() - w / 2, y, w, self.PILL_H)
        self._pill = QRectF(pill)      # 命中測試用的是真的畫出來的位置

        if self.phase == "waiting":
            # 會呼吸的光暈：告訴人「這裡可以點」。用正弦而不是彈簧——
            # 它要一直循環，彈簧是給「有目標值」的動作用的。
            pulse = 0.5 + 0.5 * math.sin(self.t * 3.4)
            p.setPen(QPen(QColor(sw.C_ACCENT.red(), sw.C_ACCENT.green(),
                                 sw.C_ACCENT.blue(), int(40 + 90 * pulse)),
                          2 + 2 * pulse))
            p.setBrush(Qt.NoBrush)
            grow = 4 + 4 * pulse
            p.drawRoundedRect(pill.adjusted(-grow, -grow, grow, grow),
                              (self.PILL_H + grow * 2) / 2,
                              (self.PILL_H + grow * 2) / 2)

        pg = QLinearGradient(pill.left(), pill.top(), pill.left(), pill.bottom())
        pg.setColorAt(0.0, QColor(30, 31, 36, 246))
        pg.setColorAt(1.0, QColor(14, 15, 18, 246))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(pg))
        p.drawRoundedRect(pill, self.PILL_H / 2, self.PILL_H / 2)

        done = self.phase == "done"
        cup_w = pixelface.cup_size(self.CUP_CELL)[0]
        pixelface.draw_cup(p, int(pill.left() + 10 + cup_w / 2),
                           int(pill.center().y()),
                           1.0 if done else 0.22,
                           "SATISFIED" if done else "THIRSTY", pixelface.GLASS,
                           pixelface.WATER_DONE if done else pixelface.WATER,
                           pixelface.INK, cell=self.CUP_CELL)

        # **進度點，不寫字。** 這張圖要說的是「它會出現、點一下就走」，
        # 訊息內容不在說明範圍內；而且縮小之後的字比杯子還難認，
        # 讀的人會停下來辨識它，注意力就從動作跑到文字上了。
        # 點數是真的資訊：點一下就多亮一格，那是這個工具唯一的計數方式。
        if openness > 0.35:
            base = p.opacity()
            p.setOpacity(base * clamp((openness - 0.35) / 0.4, 0.0, 1.0))
            filled = self.DOTS_AFTER if done else self.DOTS_BEFORE
            span = self.DOTS * self.DOT_D + (self.DOTS - 1) * self.DOT_GAP
            dx = pill.right() - 10 - span
            for i in range(self.DOTS):
                on = i < filled
                p.setBrush(QBrush(pixelface.WATER_DONE if (on and done)
                                  else pixelface.WATER if on
                                  else QColor(255, 255, 255, 55)))
                p.drawEllipse(QRectF(dx, pill.center().y() - self.DOT_D / 2,
                                     self.DOT_D, self.DOT_D))
                dx += self.DOT_D + self.DOT_GAP
            p.setOpacity(base)

        # 假游標只在循環展示時畫；互動時使用者自己的游標就在畫面上。
        if not self.interactive and self.phase in ("pointing", "done"):
            self._draw_cursor(p, pill, done)

    def _draw_screen(self, p):
        """一台縮小的電腦：外框、桌布。回傳螢幕內容的矩形。

        **只畫上半台。** 下緣由 paintEvent 羽化掉——這張圖要說的事情全部發生在
        螢幕頂端，把整台畫完只是把重點縮小。切一半再淡出，讀的人自己會補完
        「下面還有」，而且視線留在上緣。
        """
        outer = QRectF(0, 0, self.W, self.H)
        # 外框用接近真的螢幕邊框的深色，**兩個主題都一樣，不跟著翻**：
        # 它代表的是一台實體螢幕，不是介面的一部分。
        # 第一版給了中性灰（52,55,63），跟桌布的深藍太接近，整塊讀起來像一張卡片
        # 而不是一台螢幕——邊框要夠深，桌布才會被看成「亮起來的那一面」。
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(22, 24, 28)))
        p.drawRoundedRect(outer, 14, 14)
        # 頂緣一道極淡的高光，塑膠外殼的反光。少了它整塊會像一個洞。
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(outer.adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)

        screen = QRectF(self.BEZEL, self.BEZEL,
                        self.W - self.BEZEL * 2, self.H - self.BEZEL)
        if self._wall is None:
            self._wall = self._build_wallpaper(int(screen.width()),
                                               int(screen.height()))
        path = QPainterPath()
        path.addRoundedRect(screen, 6, 6)
        p.save()
        p.setClipPath(path)
        p.drawPixmap(int(screen.left()), int(screen.top()), self._wall)
        p.restore()
        return screen

    @classmethod
    def _build_wallpaper(cls, w, h):
        """像素版的 Bliss（Windows XP 那張綠丘藍天）。

        **畫成像素而不是照片或平滑漸層**：這台螢幕裡站的是一隻像素杯子，
        桌布用照片會變成兩種畫風貼在一起——`pixelface` 當初不用向量杯子配像素臉，
        也是同一個理由。

        整張預先畫一次存成 pixmap。逐格重畫的話是每秒二十幾萬次 fillRect，
        而它從頭到尾都不會變。
        """
        CELL = 4
        SKY = [QColor(38, 90, 190), QColor(58, 118, 214), QColor(94, 156, 232),
               QColor(140, 194, 242), QColor(190, 224, 248)]
        HILL = [QColor(140, 198, 63), QColor(107, 168, 46), QColor(78, 140, 34)]
        CLOUD = QColor(255, 255, 255)
        CLOUD_SHADE = QColor(214, 233, 250)

        cols, rows = -(-w // CELL), -(-h // CELL)
        pm = QPixmap(w, h)
        pm.fill(SKY[0])
        p = QPainter(pm)
        p.setPen(Qt.NoPen)

        # 地平線放在可視區的下緣附近：這張圖的重點在螢幕頂端，
        # 山丘只要露出一角就夠了，剩下的交給羽化。
        base = rows * 0.74
        amp = rows * 0.22

        for r in range(rows):
            band = min(len(SKY) - 1, int(r / max(1, base) * len(SKY)))
            p.setBrush(QBrush(SKY[band]))
            p.drawRect(0, r * CELL, w, CELL)

        # 雲：幾團手排的像素塊，不用亂數——亂數畫出來的雲每次建置都不一樣，
        # 而且多半像雜訊。(起始格, 列, 長度) 三個一組。
        for cx, cy, run, shade in ((6, 2, 9, False), (4, 3, 13, False),
                                   (7, 4, 8, True),
                                   (58, 1, 7, False), (56, 2, 11, False),
                                   (59, 3, 6, True),
                                   (88, 4, 10, False), (86, 5, 14, False),
                                   (89, 6, 8, True)):
            p.setBrush(QBrush(CLOUD_SHADE if shade else CLOUD))
            p.drawRect(cx * CELL, cy * CELL, run * CELL, CELL)

        # 山丘：從左高往右低掃過去，那是 Bliss 的構圖。
        for c in range(cols):
            t = c / max(1, cols - 1)
            top = int(base - amp * (1.0 - t) ** 1.7)
            for r in range(top, rows):
                depth = r - top
                p.setBrush(QBrush(HILL[0] if depth == 0 else
                                  HILL[1] if depth <= 2 else HILL[2]))
                p.drawRect(c * CELL, r * CELL, CELL, CELL)
        p.end()
        return pm

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


class CupPortrait(sw.Graphic):
    """杯子本人，站在牠講話的那幾頁旁邊。

    **不是裝飾，是在回答「我」是誰。** 前兩頁用第一人稱講了六次「我」，
    但讀的人要到第三頁的動畫才看得到那是什麼。把臉放在講話的旁邊，
    那六個「我」當場就有了對象。

    ## 不放在深色方塊裡

    初版把杯子畫在一個深色圓角方塊上，理由是 pixelface 的顏色是為深色藥丸調的。
    但那塊近黑的方塊貼在白卡片上像貼紙，而且它在卡片（本身也是圓角容器）裡面
    又是一層圓角容器——**框裡面again放框**，這一頁所有排版問題的共同來源。

    改成杯壁顏色跟著主題走。臉本來就畫在藍色水面上，深淺兩色都讀得到，
    只有杯壁需要調：原本的近白色在白卡片上幾乎看不見（實測比過四個色階）。
    """

    # 淺色主題的杯壁。原本的 pixelface.GLASS 是 #CED4E0，那是配深色藥丸的，
    # 放在 #FEFEFE 的卡片上淡到看不出輪廓。
    GLASS_LIGHT = QColor(139, 150, 172)
    # 水位 0.8 不是狀態，是**為了看得出那是一個杯子**。滿水（1.0）會把整個杯子
    # 填成一塊藍色，杯壁跟水同高，讀起來是方塊不是杯子；0.8 露出杯緣，
    # 一眼就知道是容器。再低（0.65 以下）水面會切過眼睛，臉就糊了。
    #
    # 選 0.8 而不是更低還有一個理由：**水位在這個程式裡是有意義的**
    # （忽略提醒它就一格一格少），畫得太低等於在暗示「快沒水了，你快點」，
    # 那是前面特地拿掉的情勒。此刻使用者什麼都還沒忽略，畫成缺水也不是事實。
    LEVEL = 0.8

    def __init__(self, cell=6, state=pixelface.NORMAL, level=LEVEL):
        super().__init__(*pixelface.cup_size(cell))
        self.cell, self.state, self.level = cell, state, level

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setOpacity(clamp(ease(self.reveal), 0.0, 1.0))
        glass = pixelface.GLASS if sw.PAL.dark else self.GLASS_LIGHT
        pixelface.draw_cup(p, self.width() // 2, self.height() // 2,
                           self.level, self.state, glass,
                           pixelface.WATER, pixelface.INK, cell=self.cell)


def _speech(text, lead=None):
    """名字一行，台詞接在下面。

    **名字單獨一行、用強調色**是對話遊戲最好認的結構特徵，比對話框的外框更關鍵。
    而且它順便回答了「說話的是誰」——前兩頁講了六次「我」，本來都沒有對象。

    名字與台詞的間距用 S1（4），跟設定頁 LABEL_GAP 同一個道理：
    它們是同一組，要貼緊；真正需要距離的是這一組跟下一組之間。
    """
    body = lead if lead is not None else sw.para(text)
    return sw.col(sw.Label(NAME, "caption", sw.C_ACCENT.name()), body,
                  spacing=sw.S1)


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
    """四頁引導。第二頁只在回答「還沒有」時出現。

    最後一頁是**真的點一次**：看過跟做過是兩回事，而這個工具唯一的操作就是
    「點一下」。演完之後讓他自己做一遍，那一下才會留在手上。
    """

    finished = Signal(bool)          # 參數：開機時啟動要不要開

    def __init__(self, on_practice=None):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("喝水提醒動態島")
        self._drag = None

        self.preview = IslandPreview()      # 第三頁，循環展示
        self.on_practice = on_practice      # 第四頁叫真的島出來，見 _page_try
        self.autostart = sw.Toggle(True)

        # 視窗自己排幾何，不掛 layout。掛了的話 Deck 的高度變化會回頭去改視窗的
        # 最小／最大高度，跟這裡逐格設定的高度打架，動畫會抖。
        self.deck = Deck(WIDTH - PAD * 2)
        self.deck.setParent(self)
        for page in (self._page_water(), self._page_fill(), self._page_howto(),
                     self._page_try()):
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

    def _page(self, title, blocks, actions, portrait=None):
        """一頁：標題、內容、右下角的動作。

        `portrait` 給的話，整個內文區改成兩欄：左欄是標題與台詞，右欄站著杯子。

        **不用負邊距去做「角色壓過內容上緣」那個效果。** 那是對話遊戲的常見手法，
        但負邊距等於在網格外面偷位置，之後任何一次改字級都會讓它錯位。
        分兩欄之後，杯子自然就比左欄的文字高出一截——同樣的視覺效果，
        每一段間距都還落在 S1/S3/S4 上。
        """
        page = QWidget()
        page.setAttribute(Qt.WA_TranslucentBackground)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(sw.S3)

        head = sw.Label(title, "title", sw.INK)
        if portrait is None:
            lay.addWidget(head)
            for b in blocks:
                lay.addWidget(b)
        else:
            body = sw.col(head, *blocks, spacing=sw.S3)
            lay.addWidget(sw.row((body, 1), portrait, spacing=sw.S4,
                                 align=Qt.AlignTop))
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
            _speech(WATER_LEAD),
            sw.Label("桌上現在有水嗎？", "headline", sw.INK),
        ], [no, yes], portrait=CupPortrait(cell=6))

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
        # 這一頁的杯子跟第一頁同一個樣子（笑臉、同樣的水位）。特別**不要**在這裡
        # 畫一個快沒水的杯子催他快去，理由見 CupPortrait.LEVEL。
        return self._page("先去裝一壺", [_speech(None, self.fill_lead)], [ok],
                          portrait=CupPortrait(cell=6))

    def _page_howto(self):
        nxt = Button("下一步")
        nxt.clicked.connect(lambda: self._go(3))
        return self._page("這樣用", [
            self.preview,
            # 三條是同一組，行距要比它們跟上下文的距離短。用頁面的 S3 排會讓
            # 三條各自讀成一段，掃過去像三件無關的事。
            sw.col(*[_bullet(t) for t in HOW_BULLETS], spacing=sw.S2),
            sw.Divider(),
            # 把「在哪裡」也寫出來。這個程式平常完全隱藏，
            # 使用者不會自己想到齒輪在紀錄視窗右上角。
            sw.para(HOW_SETTINGS),
        ], [nxt])

    def _page_try(self):
        """在**真的島**上點一次。

        **這一頁沒有示意圖。** 前一頁已經演過它長什麼樣子；這一步要練的是
        「把游標移到螢幕上緣那顆藥丸、按下去」，而**位置是這個動作的一半**——
        在引導視窗裡點一張縮小的圖，練不到那半。所以這裡叫真的島出來。

        **不擋**：「開始」隨時可以按，跟第二頁的「裝好了」同一條原則。
        這一步是給手的，不是關卡；擋住只會讓想跳過的人更想關掉程式。
        """
        start = Button("開始")
        start.clicked.connect(self._finish)
        self.try_lead = sw.para(TRY_LEAD)
        return self._page("試一次", [
            _speech(None, self.try_lead),
            sw.setting_row("開機時啟動", self.autostart),
        ], [start], portrait=CupPortrait(cell=6))

    def _on_tried(self):
        self.try_lead.setText(TRY_DONE)
        self.deck.remeasure(3)
        self._h_from = self._h_to = self.deck.natural()
        self._apply_height()

    # ------------------------------------------------------------ 流程

    def _go(self, index):
        if index == self.deck.index:
            return
        self.deck.show_page(index)
        # 展示動畫只在第三頁跑，離開就停：常駐工具不能為了看不見的動畫一直重繪。
        self.preview.stop()
        if index == 2:
            self.preview.start()
        elif index == 3 and self.on_practice:
            # 叫真的島出來讓他練習。點下去由島自己處理，不計數也不落檔，
            # 完成之後回呼到 _on_tried 換文案。
            self.on_practice(self._on_tried)
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


def open_window(on_finished, on_practice=None):
    """開引導視窗。回傳視窗物件，呼叫端要留參考否則會被回收。

    `on_practice(done_cb)` 由島提供：第四頁會叫它，讓真的島出來讓人點一次。
    沒給的話那一頁就只有文字（測試與單獨執行 onboard.py 時是這條路）。
    """
    typeface.ensure_loaded()
    win = OnboardWindow(on_practice=on_practice)
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

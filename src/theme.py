# -*- coding: utf-8 -*-
"""深色／淺色主題。

## 為什麼是「兩層表面」而不是「一個背景色」

Raycast 的淺色設定視窗（本專案的參考）不是一片白，是兩層：
外框那層偏灰（#EAEAEA），內容卡片是近白（#FEFEFE）。層次靠表面亮度分開，
不是靠描邊。深色主題本來就是這樣做的（背景 #1C1D22、卡片 #222329），
所以兩套主題共用同一組語彙，只是把亮度反過來。

## 三個函式收掉大部分的顏色

盤點原本寫死的 42 處顏色，其實只有三種角色：

- `veil(a)`   疊在底色上的薄膜：分隔線、空槽、軌道、外框。
              深色主題用白色疊亮，淺色主題用黑色壓暗——同一個 alpha 不能共用，
              黑色薄膜在淺底上比白色薄膜在深底上明顯得多，所以要打折。
- `ink_a(a)`  帶透明度的文字色。
- 語意色       accent / green / flame / danger。這些在兩套主題不是同一個值：
              #4FA8E8 放在近白底上對比只有 2.4:1，當文字讀不到，淺色版要壓深。

剩下的是真正跟主題無關的東西（例如週曆上打勾的深色筆畫，兩邊都畫在彩色圓點上）。

## 島不換主題

島是浮在任意畫面上的 HUD，深色是對的——它要在任何桌布上都讀得到，
而且它的狀態顏色（黃、橘紅、灰、綠）是校準在深色藥丸上的。
主題只作用在紀錄／設定視窗。
"""

from PySide6.QtGui import QColor


class Palette:
    VEIL_FLOOR = 20        # 淺色主題下，薄膜再淡也不能低於這個值

    def __init__(self, name, dark, bg, card, ink_rgb, accent, green,
                 flame, flame2, danger, veil_scale, gloss, shadow_peak):
        self.name = name
        self.dark = dark
        self.bg_top, self.bg_bottom = (QColor(c) for c in bg)
        self.card_top, self.card_bottom = (QColor(c) for c in card)
        self.ink_rgb = ink_rgb
        self.accent = QColor(accent)
        self.green = QColor(green)
        self.flame = QColor(flame)
        self.flame2 = QColor(flame2)
        self.danger = QColor(danger)
        self._veil_scale = veil_scale
        self._gloss = gloss
        self.shadow_peak = shadow_peak

    # ---- 薄膜 ----

    def veil(self, alpha):
        """疊在底色上的一層薄膜。深色主題疊白、淺色主題疊黑。

        alpha 傳的是「深色主題下的值」，淺色主題會自動打折——
        直接沿用同一個數字，淺色版的分隔線會粗得像被畫了框。
        """
        if self.dark:
            return QColor(255, 255, 255, alpha)
        # 淺色主題除了打折還要有下限。空槽那一族原本用 14–18 的極淡白，
        # 打完折剩 10–13 的黑，在 #FEFEFE 上等於不存在——
        # 「還沒達成的那幾格」看不見的話，進度就只剩已完成的部分，讀不出還差多少。
        return QColor(0, 0, 0, max(self.VEIL_FLOOR, int(alpha * self._veil_scale)))

    @property
    def seg_pill(self):
        """分段控制項裡「選中」那一格的底色。

        兩套主題的做法是相反的，不是同一個值換亮度：
        深色主題把選中格疊亮（白色薄膜）；淺色主題要疊白才對——
        在淺灰軌道上放一塊近白，才是淺色介面裡「這格被選中」的標準長相。
        照抄深色的做法（黑色薄膜）會得到灰底上一塊更深的灰，讀起來像被停用。
        """
        return QColor(255, 255, 255, 34) if self.dark else QColor(255, 255, 255, 235)

    def gloss(self, alpha):
        """卡片頂緣的高光。淺色主題直接關掉：
        在 #FEFEFE 上再加白光是看不見的，只會讓漸層邊緣出現髒帶。
        """
        return QColor(255, 255, 255, int(alpha * self._gloss))

    # ---- 文字 ----

    def ink_a(self, alpha255):
        r, g, b = self.ink_rgb
        return QColor(r, g, b, alpha255)

    def css(self, opacity):
        r, g, b = self.ink_rgb
        return f"rgba({r},{g},{b},{opacity})"

    @property
    def ink(self):
        return self.css(1)

    @property
    def ink2(self):
        # 深色底用灰階抗鋸齒，字本來就偏細，壓太低會讀不到（見 stats_window 說明）。
        # 淺色底沒有這個問題，可以壓得比深色版低一點而仍然清楚。
        return self.css(0.84 if self.dark else 0.72)

    @property
    def ink3(self):
        return self.css(0.74 if self.dark else 0.55)


DARK = Palette(
    name="dark", dark=True,
    bg=("#1C1D22", "#0E0F12"),
    card=("#222329", "#17181D"),
    ink_rgb=(235, 235, 245),
    accent="#4FA8E8", green="#4FCF8A",
    flame="#FF9F43", flame2="#FFD166", danger="#E87A4F",
    veil_scale=1.0, gloss=1.0, shadow_peak=0.34,
)

# 對齊 Raycast 的淺色設定視窗：外框 #EAEAEA、卡片 #FEFEFE。
# 語意色全部壓深——原本那組是校準在深色底上的，放到近白底上對比不足。
# 外框 #EAEAEA、卡片 #FEFEFE：兩層之間差 20 階。
# 第一版給 #EFEFEF 只差 8 階，卡片浮不起來——淺色主題的層次全靠這個差值，
# 深色主題可以再靠頂緣高光補，淺色沒有那個工具（白光加在近白上是看不見的）。
LIGHT = Palette(
    name="light", dark=False,
    bg=("#EAEAEA", "#E3E3E4"),
    card=("#FEFEFE", "#F8F8F9"),
    ink_rgb=(28, 28, 30),
    accent="#1B7FD4", green="#22A06B",
    flame="#E07B1F", flame2="#F0B429", danger="#C94820",
    veil_scale=0.72, gloss=0.0, shadow_peak=0.15,
)

_PALETTES = {"dark": DARK, "light": LIGHT}
_active = DARK


def active():
    return _active


def resolve(name):
    """把設定值換成實際要用的調色盤。'auto' 跟隨系統。"""
    if name in _PALETTES:
        return _PALETTES[name]
    return _system_palette()


def _system_palette():
    """問系統現在是不是深色模式。問不到就用深色——這個程式原本就是深色的。"""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
        scheme = QGuiApplication.styleHints().colorScheme()
        return LIGHT if scheme == Qt.ColorScheme.Light else DARK
    except (ImportError, AttributeError):
        return DARK


def apply(name):
    """切換主題，回傳實際生效的調色盤。"""
    global _active
    _active = resolve(name)
    return _active

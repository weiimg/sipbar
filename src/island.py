# -*- coding: utf-8 -*-
"""Sipbar（喝水提醒動態島）— 正式版

把 pet.py 的計時、閒置偵測、事件紀錄，搬進 island_prototype.py 的動態島形式。

行為：
    正常／達標  -> 完全隱藏，螢幕零佔用
    口渴／虛弱  -> 從螢幕頂端滑下來，停在各自的停留尺寸，趕不走
    倒地        -> 全展開，不收合也不消失
    喝了        -> 閃一下確認訊息，然後滑上去消失

「消失」是獎勵，不是逃生出口——沒有關閉按鈕，只能靠喝水讓它走。

計時基準是「在電腦前的連續時間」，不是牆上時鐘：鍵鼠閒置就暫停計時。
提醒發在你不能行動的時候只會訓練出無視的反射，那個反射會污染你對所有提醒的反應。

用法：
    run.bat            日常用這個（無 console）
    python island.py   第一次跑或出錯時用這個，才看得到錯誤訊息

隱藏時所有操作都在系統匣圖示：左鍵＝補水一次，右鍵＝選單。
"""

import ctypes
import json
import os
import random
import sys
import time
from ctypes import wintypes
from datetime import datetime, timedelta

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QFont, QFontMetrics, QIcon, QLinearGradient,
    QPainter, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QWidget

import crashlog                               # 閃退時把 traceback 留下來
import pixelface                              # 像素杯與表情
import settings                               # 路徑、設定、推導、開機自啟
import typeface                               # 隨程式散布的字體
from motion import Spring, clamp, lerp        # 彈簧與紀錄視窗共用同一套物理
from paintkit import draw_soft_shadow, shadow_alphas

APP_NAME = settings.APP_NAME
APP_TITLE = settings.APP_TITLE          # 招牌上的字；APP_NAME 是資料夾名，兩者不同
# 路徑與設定的唯一事實來源在 settings.py。這裡 import 成模組層級的名字，
# 是為了讓測試可以照舊 monkeypatch isl.STATE_PATH / isl.EVENTS_PATH 指到暫存資料夾。
DATA_DIR = settings.DATA_DIR
STATE_PATH = settings.STATE_PATH
EVENTS_PATH = settings.EVENTS_PATH
ICON_PATH = os.path.join(settings.resource_dir(), "assets", "icon.ico")

DEFAULT_CONFIG = settings.DEFAULTS      # 預設值與說明都在 settings.py

NORMAL, THIRSTY, WEAK, COLLAPSED, SATISFIED = "NORMAL", "THIRSTY", "WEAK", "COLLAPSED", "SATISFIED"
REMINDING = (THIRSTY, WEAK, COLLAPSED)

PILL_TOP = 10
PILL_MIN = (116, 36)
PILL_MAX = (462, 100)   # 留餘裕給「連續 100 天 · 下次約 100 分後」這種最長情況

# 視窗必須容得下：藥丸本體 + 擠壓拉伸的額外寬度 + 陰影 + 邊界餘裕。
# 只改藥丸寬度而忘了視窗，圓角會被視窗邊界直接切掉——這正是踩過的坑。
SQUASH_MAX = 16         # pill_rect() 裡擠壓效果的上限
# 陰影半徑要跟 sigma 相稱：sigma=7 時 d=18 的 alpha 已低於 0.012（看不見），
# 再往外畫只是白白讓遮罩吃掉更多滑鼠事件。
PILL_SHADOW = 18        # 陰影往外羽化的距離
SHADOW_SIGMA = 7.0      # 高斯衰減的標準差，越大越散
SHADOW_PEAK = 0.32      # 緊貼藥丸處的最大不透明度
SHADOW_OFFSET_Y = 5     # 光從上方來，陰影往下偏
WIN_W = PILL_MAX[0] + (SQUASH_MAX + PILL_SHADOW) * 2 + 8
WIN_H = PILL_TOP + PILL_MAX[1] + PILL_SHADOW + SHADOW_OFFSET_Y + 12
SHADOW_ALPHAS = shadow_alphas(PILL_SHADOW, SHADOW_PEAK, SHADOW_SIGMA)

# 蘋果的容器不用彩色外框標示狀態——顏色由內容承載，容器保持中性。
# 深度來自材質（漸層、頂緣高光、投影），不是描邊。
INK_PRIMARY = QColor(245, 245, 247)        # 深色模式主要文字
# 蘋果的深色次要文字規格是 60%，但那是給 ClearType 的環境。
# 半透明視窗只能用灰階抗鋸齒、字本來就偏細，壓到 60% 會變成讀不到。
INK_SECONDARY = QColor(235, 235, 245, 196)
PILL_TOP_COLOR = QColor(30, 31, 36, 246)
PILL_BOTTOM_COLOR = QColor(14, 15, 18, 246)
ACCENT = QColor("#4FA8E8")

# 把滑鼠移到螢幕頂端中央，島就滑下來（macOS 選單列那個互動）。
# 島隱藏時如果只剩系統匣可以操作，就等於把唯一入口交給一個
# Windows 預設會摺疊起來的地方——太脆弱，所以要有這條不依賴系統匣的路。
#
# 熱區初版設 110px / 4px，在 3440px 超寬螢幕上根本打不到：
# 要同時瞄準正中央 6% 的寬度和 4 像素高的一條縫。放寬成整個上緣中段。
#
# 但 320 是為 3440px 調出來的（佔 18.6%），照抄到 1920 螢幕就變成 33%——
# 整個上緣有三分之一會讓島跳出來，滑過去拿視窗按鈕都會誤觸。
# 改成跟著螢幕寬走，兩端夾住：太窄打不到，太寬會誤觸。
#
# 這兩個上下限是**實體像素**。它們講的是「手能不能瞄準」與「會不會誤觸」，
# 那是眼睛與滑鼠的事，而使用者的手是在實體像素裡移動的。
#
# 但 `peek_half_w()` 的回傳值要拿去跟 `QScreen.geometry()` 比，那是邏輯像素。
# 所以夾之前先除以 dpr 換算過去；乘回 dpr 就是使用者真正要跨過的距離，
# 在任何縮放下都是同一個實體寬度。
#
# 這件事要跟 `cursor_pos()` 一起看才完整——光把上下限換算好沒有用，
# 比較式的另一端（游標）當初回的是實體像素，兩邊座標系不同的話夾多寬都不對。
# 那個 bug 讓熱區整個偏離螢幕中央（偏到 `實體寬 /(2×dpr)`），
# 在 200% 縮放下照著文件瞄準上緣正中央永遠叫不出島。理由見 cursor_pos()。
PEEK_HALF_MIN, PEEK_HALF_MAX = 140, 320
PEEK_WIDTH_RATIO = 0.093
PEEK_EDGE_PX = 10


def peek_half_w(screen_w, dpr=1.0):
    dpr = dpr or 1.0
    return int(clamp(screen_w * PEEK_WIDTH_RATIO,
                     PEEK_HALF_MIN / dpr, PEEK_HALF_MAX / dpr))


def target_screen(cfg):
    """設定指定的螢幕；沒指定或已拔掉就退回主螢幕。

    不能只認索引：拔插螢幕會讓索引整個位移，島就跑到別的螢幕上。
    名稱雖然也可能變，但至少不會默默指到另一台。
    """
    name = cfg.get("screen_name")
    if name:
        for s in QApplication.screens():
            if s.name() == name:
                return s
    return QApplication.primaryScreen()

# 半透明視窗用不了 ClearType 次像素渲染，Qt 只能退回灰階抗鋸齒，字會偏細偏糊。
# 補救只有三招：字重夠、尺寸用像素而非點數、位置對齊整數像素。
# 字型與字重的選擇理由見 typeface.py，字體檔隨程式散布，不再假設機器上有裝。
FONT_TITLE_PX = 20
FONT_SUB_PX = 16      # 15px 時中文筆畫密的字會糊在一起，見 stats_window.py 的說明

#              主色        停留後停在  是否現身
VISUAL = {
    NORMAL:    ("#4FA8E8", 0.00, False),
    THIRSTY:   ("#E8C34F", 0.35, True),
    WEAK:      ("#E87A4F", 0.50, True),
    COLLAPSED: ("#8A8A8A", 1.00, True),
    SATISFIED: ("#4FCF8A", 1.00, True),
}

# copy-style: off
#
# 以下是角色的台詞，不是介面文案。口語、第二人稱、語助詞都是刻意的——
# 島是一個會渴會倒的東西，它說「口渴了」「你贏了」正是這個工具的設計核心。
# 介面文案（設定項、選單、按鈕）走另一套標準，見 tests/test_copy_style.py。
#
# 可預測性是習慣化的根源，所以每次隨機挑，不重複到你背起來為止。
MESSAGES = {
    THIRSTY: [
        "口渴了", "該喝水了", "水呢", "喉嚨乾乾的", "來一口",
        "水壺還有水嗎", "現在喝正好", "提醒一下：水", "喝一口再繼續",
    ],
    WEAK: [
        "真的渴了", "有點虛", "撐不太住", "還是沒喝喔", "再不喝要倒了",
        "拜託", "水……", "已經等你一陣子了", "還在等",
    ],
    COLLAPSED: [
        "倒了", "沒力了", "陣亡", "叫不動了", "放棄了",
        "你贏了", "需要急救（一杯水）", "躺平中",
    ],
    NORMAL: ["水分充足", "還沒到時間", "下次再叫你"],
}

DONE_MESSAGES = ["今天已達標", "今天不吵你了", "收工了"]

# 深夜文案（「小口就好」「淺嚐一下就好」）已移除，不是忘了寫。
# 它有 50% 機率出現，但 drink() 一律記整整一次——文案叫你喝半口，
# 帳上照樣記一份 ml_per_drink_estimate。以睡前三小時約 2.8 次估，
# 單晚高估約 173cc，等於日總量的 12.7%，而且高估的正是唯一真的需要
# 控制攝取量的那個時段，等於在最不能失真的地方失真。
# 隨機出現讓它更糟：一半叫小口一半不叫、記帳完全相同，使用者建不出心智模型。
# 不改成「算 0.5 次」——那會毀掉「次」是整數這件事，而整數正是這個工具
# 敢用「次數」而非「杯」當單位的理由（見 settings.py 的 ml_per_drink_estimate）。
# 深夜的攝取量本來就被拉長的間隔壓住了，這段文案生理上多餘、記帳上有害。
# copy-style: on




# ---------------------------------------------------------------- Windows 閒置偵測

class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", _RECT),
                ("rcWork", _RECT), ("dwFlags", wintypes.DWORD)]


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


# use_last_error=True：ctypes 預設不保存 Windows 的 last error，
# 直接呼叫 GetLastError() 可能拿到被 ctypes 內部操作蓋掉的值，單一實例鎖會不可靠。
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.GetTickCount64.restype = ctypes.c_ulonglong


def cursor_pos():
    """游標位置，**邏輯像素**，跟 QScreen.geometry() 同一個座標系。

    這裡不用 Win32 的 `GetCursorPos`。它跟旁邊那幾支不一樣——閒置偵測與單一
    實例鎖是 Qt 沒有的東西，非 ctypes 不可；游標位置 Qt 本來就有，而且只有
    Qt 這條給的是對的座標。

    Qt6 預設把程序設成 per-monitor DPI aware，於是 `GetCursorPos` 回的是
    **實體像素**，而 `QScreen.geometry()` 回的是**邏輯像素**。100% 縮放時兩者
    相同，所以這個 bug 可以躺很久不被發現；一旦使用者把顯示縮放調到 200%，
    兩個呼叫端就同時壞掉：

    - `_peek_tick` 拿實體 x 去減邏輯中心，熱區中心跑到 `實體寬 /(2×dpr)`，
      照文件瞄準螢幕上緣正中央永遠叫不出島
    - `_popup_menu` 把實體座標交給 Qt 定位選單，選單會開在別的地方

    `QCursor.pos()` 另外處理了混合 DPI 的多螢幕——那不是「除以一個 dpr」
    做得出來的，每台螢幕的換算係數不一樣。
    """
    p = QCursor.pos()
    return p.x(), p.y()


def idle_seconds():
    """距離上一次鍵盤或滑鼠輸入過了幾秒。"""
    lii = _LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    if not _user32.GetLastInputInfo(ctypes.byref(lii)):
        return 0.0
    # dwTime 是 32-bit、約 49.7 天繞回一次，所以差值要遮罩回 32-bit。
    return ((_kernel32.GetTickCount64() - lii.dwTime) & 0xFFFFFFFF) / 1000.0


def single_instance_guard():
    """島與桌寵共用同一組資料，同時跑會讓次數重複計算，所以共用一把鎖。"""
    # 名字跟著改名走。這個 mutex 只活在記憶體裡、沒有任何東西保存它，
    # 所以不需要遷移——唯一的代價是改名後第一次啟動時，若還有一個舊版程式
    # 開著，兩者的鎖名不同會同時跑。重開一次就沒事。
    _kernel32.CreateMutexW(None, False, f"{settings.APP_NAME}SingletonMutex")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


# ---------------------------------------------------------------- 設定與存檔

load_config = settings.load_config       # 含舊檔遷移與鍵名升級，見 settings.py


def day_key(now, rollover_hour):
    """一天的分界不在午夜，在早上 5 點——不然凌晨兩三點的工作會被切成兩天。"""
    d = now - timedelta(days=1) if now.hour < rollover_hour else now
    return d.strftime("%Y-%m-%d")


def load_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    """落檔要能吞掉 Windows 的暫時性鎖定。

    os.replace 會偶發 PermissionError（WinError 5）：防毒或索引服務在檔案剛寫完時
    開一個掃描用的 handle，那一瞬間覆蓋就會被拒。實測跑測試時每次掛的位置都不同，
    正是這種競態。這條路徑不能讓例外逃出去——它每分鐘跑一次，也在補水、暫停、
    結束時跑，炸掉的話累積時間就回不來，症狀會變成「倒數莫名變多」那個老問題。

    重試幾次仍失敗就放棄：最多丟掉一分鐘，比讓例外往上炸好。
    """
    settings.guard_real_write(STATE_PATH)
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        for attempt in range(6):
            try:
                os.replace(tmp, STATE_PATH)
                return
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.03)
    except OSError:
        pass


def log_event(day, event, **fields):
    settings.guard_real_write(EVENTS_PATH)
    os.makedirs(DATA_DIR, exist_ok=True)
    row = {"ts": datetime.now().isoformat(timespec="seconds"), "day": day, "event": event}
    row.update(fields)
    try:
        with open(EVENTS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------- 彈簧

# ---------------------------------------------------------------- 主體

class Island(QWidget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.state = NORMAL
        self.active_s = 0.0          # 「在電腦前」的累積秒數，不是牆上時鐘
        self.paused_until = None
        self.streak = 0
        self.message = ""
        self.sub_message = ""
        self._hover = False
        self._peeking = False
        # 防連點用的時間戳。給一個很早的值，程式一啟動就能記第一次補水。
        self._last_drink_at = -1e9
        self._peek_locked = False
        self._greeting = False
        # 引導最後一步用的練習模式。開著的時候 drink() 走一條不寫入任何東西的路，
        # 見 practice()。
        self._practicing = False
        self._practice_cb = None
        self._restored_state = None      # 上次關掉時停在哪個提醒狀態

        now = datetime.now()
        saved = load_state()
        self.day = day_key(now, settings.DAY_ROLLOVER_HOUR)
        same_day = saved.get("day") == self.day
        self.drinks = saved.get("drinks", 0) if same_day else 0
        if not same_day:
            log_event(self.day, "day_start", target=cfg["daily_target_drinks"])

        # 計時必須跨重啟保存。不存的話，每次開機自啟或程式意外結束，
        # 累積的在電腦前時間就歸零、間隔還會重新擲一次——提醒被無限往後推，
        # 而且探頭看到的倒數會莫名其妙變多。
        self._restore_timing(saved, same_day, now)
        self._persist_countdown = 0
        self._refresh_streak()

        self.sp_expand = Spring(0.0)
        self.sp_reveal = Spring(0.0)
        self.sp_content = Spring(0.0)
        self.sp_pulse = Spring(1.0, 0.28, 0.55)   # 按下去的回彈，蘋果一定會回應觸碰
        # 水位獨立一條彈簧：狀態一變就改目標，轉場自動平滑、可被打斷，
        # 跟島上其他東西同一套物理。阻尼給滿，水不該彈過頭再回來。
        self.sp_level = Spring(pixelface.LEVEL[NORMAL], 0.55, 1.0)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.resize(WIN_W, WIN_H)
        self._reposition()

        self._f_title = self._make_font(FONT_TITLE_PX, QFont.Bold)
        self._f_sub = self._make_font(FONT_SUB_PX, QFont.Medium)   # 深色底補償，不用 Regular

        self._last = time.perf_counter()
        self.frame = QTimer(self)
        self.frame.setInterval(16)           # 60fps，但只在動的時候跑
        self.frame.timeout.connect(self._step)

        self.hold_timer = QTimer(self)
        self.hold_timer.setSingleShot(True)
        self.hold_timer.timeout.connect(self._settle)

        # 內容延遲進場專用。必須是可取消的計時器，理由見 _target_content()。
        self._content_pending = 0.0
        self._content_delay = QTimer(self)
        self._content_delay.setSingleShot(True)
        self._content_delay.timeout.connect(self._apply_pending_content)

        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start(int(cfg["tick_seconds"] * 1000))

        self.peek_timer = QTimer(self)
        self.peek_timer.timeout.connect(self._peek_tick)
        self.peek_timer.start(120)      # 太慢會漏掉快速掃過熱區的移動

        self.tray = self._build_tray()
        self._refresh_message()
        # 接回上次的提醒狀態。從 NORMAL 起算的話，tick() 會發現 active_s 已經
        # 超過間隔而立刻再發一次提醒——每次重開都多念一遍，還會污染活動紀錄。
        # animate=False：這是還原不是新事件，不該滑下來吸引注意。
        self._enter(self._restored_state or NORMAL, animate=False)
        self._persist()      # 啟動就先落檔，否則第一分鐘內被關掉會什麼都沒存到

    def _reposition(self):
        """把島貼到指定螢幕的頂端中央。換螢幕的設定改完要重叫一次。

        `scr.center().x()` 是那台螢幕自己的中心——21:9 算 1720、16:9 算 960，
        跟長寬比與解析度都無關。

        ## 執行期間改顯示縮放不會跟上，這是已知限制

        試過三種修法，三種都不行，記在這裡免得有人再走一次：

        1. 掛 `QScreen.geometryChanged` / `logicalDotsPerInchChanged` 重算——
           訊號有響，但重算出來的位置照樣錯（見第 3 點）。
        2. 在 `show()` 之前重算——那時候視窗的比例還沒更新，等於用舊比例算。
        3. 顯示之後用 Win32 的 `GetWindowRect` 量實際落點再補差值——**位置修好了，
           但尺寸還是錯的**（100% 下視窗仍是 673px，該是 538），對齊之後反而更明顯。

        根因是同一個：`QScreen` 的資料在 DPI 變更後是正確的（實測 100/125/150/
        175/200% 每一級都跟得上），但 Qt 把邏輯座標與尺寸換算成實體像素時，用的是
        **視窗自己記著的比例**，而那個比例來自 Windows 的 WM_DPICHANGED——
        **隱藏的視窗收不到那則通知，而且一旦過期就不會自己恢復。**

        要真的修得銷毀並重建原生視窗，那是核心元件的生命週期，代價不對等。
        重開程式就正常，已知限制寫在 docs/USAGE.md。
        """
        scr = target_screen(self.cfg).geometry()
        self.move(scr.center().x() - WIN_W // 2, scr.top())

    # ------------------------------------------------------------ 設定

    def apply_config(self, cfg):
        """設定改完即時生效。但節奏類的變更一律等下一輪。

        如果改間隔會重擲當前這一輪的倒數，使用者就學會了「快渴的時候
        去設定裡動一下」把提醒推回去——那是一個藏在設定裡的 dismiss 後門，
        整個工具的前提是「你無法 dismiss 一個狀態」，不能自己開一個洞。
        所以這裡不碰 self.interval_s，下一次補水重擲時新值才會生效。

        設定變更會落進事件紀錄。不阻止使用者把目標從 10 調到 3——
        那是他的自我追蹤，不是考試——但熱力圖要看得出那天標準換過。
        """
        # 舊值一定要先複製一份。只存參考的話，只要呼叫端跟島共用同一個字典
        # （紀錄視窗曾經就是），舊值會在比對之前就被就地改成新值，
        # `changed` 永遠是空的 -> 直接 return -> 換螢幕、改目標全部沒有作用，
        # 而且連一行事件紀錄都不會留下。實測就是這樣壞掉的。
        old = dict(self.cfg)
        self.cfg = dict(cfg)
        changed = {k: (old.get(k), self.cfg.get(k))
                   for k in set(old) | set(self.cfg) if old.get(k) != self.cfg.get(k)}
        if not changed:
            return

        log_event(self.day, "config", changed={k: v[1] for k, v in changed.items()})

        if "tick_seconds" in changed:
            self.tick_timer.setInterval(int(self.cfg["tick_seconds"] * 1000))
        if "screen_name" in changed:
            self._reposition()
        if "daily_target_drinks" in changed:
            # 目標變了，連續天數的判定跟著變，島上的數字要當場更新
            self._refresh_streak()
            # 新目標可能當場就已經達成。tick 五秒後也會收，但改完設定馬上看到
            # 才是對的回饋。
            self._dismiss_if_done()
        self._refresh_message()
        self._sync_tray()
        self.update()

    # ------------------------------------------------------------ 動畫

    def _kick(self):
        if not self.frame.isActive():
            self._last = time.perf_counter()
            self.frame.start()

    def _step(self):
        now = time.perf_counter()
        dt, self._last = now - self._last, now

        for s in (self.sp_expand, self.sp_reveal, self.sp_content, self.sp_pulse,
                  self.sp_level):
            s.step(dt)

        if self.sp_reveal.value > 0.005 and not self.isVisible():
            # 要現身之前重算一次。位置只有在看得見的時候才有意義，
            # 而它隱藏的時間遠比出現的時間長——螢幕在那期間換了、DPI 變了、
            # 筆電接上外接螢幕了，都不會有事件送到一個不在畫面上的視窗。
            self.show()
        elif self.sp_reveal.target == 0.0 and self.sp_reveal.value <= 0.005 and self.isVisible():
            self.hide()

        self._apply_mask()
        self.update()

        springs = (self.sp_expand, self.sp_reveal, self.sp_content, self.sp_pulse,
                   self.sp_level)
        if all(s.settled for s in springs):
            for s in springs:
                s.value, s.velocity = s.target, 0.0
            self.frame.stop()
            self.update()

    def _target_expand(self, value):
        """展開彈跳、收合平順——展開是要抓注意力，收合是要讓開。"""
        if value > self.sp_expand.value:
            self.sp_expand.tune(0.40, 0.70)
        else:
            self.sp_expand.tune(0.52, 1.00)
        self.sp_expand.target = value
        self._kick()

    def _target_reveal(self, value):
        if value > self.sp_reveal.value:
            self.sp_reveal.tune(0.46, 0.72)
        else:
            self.sp_reveal.tune(0.36, 1.00)
        self.sp_reveal.target = value
        self._kick()

    def _target_content(self, value, delay_ms=0):
        """內容進場比容器慢、退場比容器快，中間才不會有東西被擠壓的感覺。

        延遲必須可取消。singleShot 排出去就收不回來，那一發會在幾十毫秒後
        無條件覆蓋掉「之後」才下的目標——滑鼠掃過藥丸（enter 完馬上 leave）時，
        _settle() 剛把內容設成 0，過期的那發又把它蓋回 1，於是藥丸縮到停留尺寸、
        字卻留在上面，被擠成「現在…」。而且它不會自己恢復，要等下一次狀態切換。

        教訓與「累積中的狀態要問程式死掉會怎樣」是同一類：任何延遲執行的東西
        都要問一句「它開火時，當初的前提還成立嗎」。
        """
        self.sp_content.tune(0.34, 1.0)
        self._content_delay.stop()           # 先撤掉還沒開火的那一發
        if delay_ms:
            self._content_pending = value
            self._content_delay.start(delay_ms)
        else:
            self.sp_content.target = value
            self._kick()

    def _apply_pending_content(self):
        self.sp_content.target = self._content_pending
        self._kick()

    # ------------------------------------------------------------ 狀態切換

    def _roll_interval(self):
        """深夜拉長間隔：睡前灌水會半夜起來上廁所，把睡眠打斷。

        深夜間隔是主間隔乘上一個倍數，不是獨立參數——兩個各自可調，
        使用者一定會調出「深夜比白天還短」這種互相矛盾的組合。
        """
        base = (settings.late_night_interval(self.cfg) if self._is_late()
                else self.cfg["interval_min"])
        # 抖動是為了對抗「整點提醒」的可預測性。
        # 改成比例而非固定分鐘：±10 分在間隔 70 分時合理，設成 30 分就太大了。
        jitter = base * self.cfg["interval_jitter_pct"] / 100.0
        return (base + random.uniform(-jitter, jitter)) * 60

    def _is_late(self, hour=None):
        hour = datetime.now().hour if hour is None else hour
        return hour >= self.cfg["late_night_start_hour"] or hour < self.cfg["day_rollover_hour"]

    def _refresh_streak(self):
        """連續天數要算在島上顯示。

        原本它只存在於紀錄視窗裡，而島上每天唯一會變的數字是「今天 N/7 次」——
        那個數字每天歸零，於是整套連續機制看起來像每天重置。
        Duolingo 的火焰有用，是因為它在你每天會看到的地方。
        """
        try:
            import dashboard
            days = dashboard.load_days(EVENTS_PATH, settings.DAY_ROLLOVER_HOUR)
            self.streak = dashboard.compute_streaks(
                days, self.cfg["daily_target_drinks"], self.day)["streak"]
        except Exception:
            self.streak = 0                       # 算不出來就不顯示，不影響提醒本身

    def _status_sub(self):
        """探頭時你想知道的是「下次什麼時候」，不是重複告訴你今天喝幾次。

        使用者得開口問「多久跳一次」，就代表這個資訊沒被放進介面。
        """
        target = self.cfg["daily_target_drinks"]
        if self.paused_until:
            return f"暫停中，{self.paused_until.strftime('%H:%M')} 恢復"
        # 底下那排進度點已經表達了今天的次數，這裡就不重複——
        # 換成連續天數，否則島上唯一會變的數字每天歸零，看起來像連續被重置了。
        head = f"連續 {self.streak} 天" if self.streak else f"今天 {self.drinks}/{target} 次"
        if self.drinks >= target:
            return f"{head}，今天已達標"
        remain = int(max(0, self.interval_s - self.active_s) // 60)
        # 分隔符用半形空白而非全形，目標次數變多時進度點會吃掉寬度，
        # 全形空白會讓這行剛好超過而被省略號截掉。
        #
        # 深夜要標示出來：抖動有 ±15%，「這次怎麼比較久」在畫面上跟深夜模式長得
        # 一模一樣，而這個機制全自動、推導可能算錯、每次啟動又無聲重算——
        # 連「它正在作用」都不顯示的話，壞掉時使用者無從歸因。
        #
        # 標示的做法是換掉「下次」這個詞，不是插入一段新的。加一段就得多一個
        # 分隔點，而最長情況（連續破百 + 三位數分鐘）只剩 34px 餘裕，插什麼都爆
        #（「深夜 · 下次約」實測 284px、可用 262px）；為了塞進去而省掉分隔點的
        # 寫法又會被讀成「放慢了 100 分」，是另一個意思。
        # 換詞則一個字都沒多：白天「下次約 N 分後」、深夜「夜間約 N 分後」，
        # 同寬同節奏，變的那個詞正好就是要傳達的資訊。
        late = self._is_late()
        if remain <= 0:
            # 這裡不標示深夜。標示是用來解釋「這個數字為什麼這麼大」的，
            # 而「快到了」沒有數字——沒有要解釋的東西就不要加字。
            return f"{head} · 快到了"
        return f"{head} · {'夜間' if late else '下次'}約 {remain} 分後"

    def _reminding_sub(self):
        target = self.cfg["daily_target_drinks"]
        if self.streak:
            return f"連續 {self.streak} 天 · 今天 {self.drinks}/{target} 次"
        return f"今天補水 {self.drinks}/{target} 次"

    def _refresh_message(self, override=None, sub=None):
        # 小標只放狀態，不放操作說明。「點一下就算喝了」學會之後就只是噪音，
        # 常駐的介面文字要能一直被讀，不能是一次性的教學。
        if sub:
            self.sub_message = sub
        elif self.state == NORMAL:
            self.sub_message = self._status_sub()
        else:
            self.sub_message = self._reminding_sub()

        if override:
            self.message = override
        elif self.state == NORMAL and self.drinks >= self.cfg["daily_target_drinks"]:
            self.message = random.choice(DONE_MESSAGES)
        else:
            self.message = random.choice(MESSAGES.get(self.state, MESSAGES[NORMAL]))

    def _hold_for(self, state):
        return {
            THIRSTY: self.cfg["thirsty_hold_seconds"],
            WEAK: self.cfg["weak_hold_seconds"],
            SATISFIED: self.cfg["satisfied_flash_seconds"],
        }.get(state, 0)

    def _enter(self, state, animate=True, message=None, sub=None):
        self.state = state
        self._refresh_message(message, sub)
        self.sp_level.target = pixelface.LEVEL.get(state, 1.0)
        self._kick()
        self.hold_timer.stop()
        if VISUAL[state][2]:
            self._peeking = False       # 真的該現身時，探頭狀態讓位

        if not VISUAL[state][2]:
            self._target_content(0.0)
            self._target_expand(0.0)
            self._target_reveal(0.0)
            self._sync_tray()
            return

        self._target_reveal(1.0)
        self._target_expand(1.0)
        self._target_content(1.0, delay_ms=90)   # 容器先動，字後到

        hold = self._hold_for(state)
        if hold > 0:
            self.hold_timer.start(int(hold * 1000))

        if not animate:
            for s in (self.sp_expand, self.sp_reveal, self.sp_content, self.sp_level):
                s.value = s.target
        self._sync_tray()

    def greet(self):
        """啟動時自己現身幾秒。

        一個平常完全隱藏的工具，最大的問題是使用者根本不知道它在哪、
        甚至不知道它有沒有在跑。與其叫人去翻系統匣，不如讓它自己出來打個招呼。
        """
        self._greeting = True
        self._peeking = True
        # 主字是角色的聲音，副字是操作說明——兩者語域不同是刻意的：
        # 島可以有個性，但「怎麼叫出它」必須是清楚的指示。
        # copy-style: off
        self.message = "嗨！"
        # copy-style: on
        self.sub_message = "游標移至螢幕上緣中央可呼叫"
        self._target_reveal(1.0)
        self._target_expand(1.0)
        self._target_content(1.0, delay_ms=90)
        QTimer.singleShot(4000, self._end_greet)

    def _end_greet(self):
        self._greeting = False
        if self._hover or VISUAL[self.state][2]:
            return
        self._peeking = False
        self._target_content(0.0)
        self._target_expand(0.0)
        self._target_reveal(0.0)

    def _menu_open(self):
        """自己的右鍵選單正開著。

        選單畫在島的下方，所以「把滑鼠移過去點」這個動作本身就會同時離開
        熱區、離開藥丸、觸發 leaveEvent。三條收合路徑會一起把島收掉，
        而使用者的手還在往選單移動的半路上。

        島收掉之後選單就沒有依附的東西了，看起來像整組消失；離選單越遠的
        項目越難點到，「設定」排第四，所以最常被回報成沒有反應。
        """
        m = getattr(self, "_menu_ref", None)
        return m is not None and m.isVisible()

    def _menu_dismissed(self):
        """選單關掉之後，把剛才擋下來的收合判斷補做一次。

        延一個事件迴圈再跑：closed 是在 closeEvent 裡發的，那時候 isVisible()
        還是 True，直接判斷會以為選單仍然開著。
        """
        if self._hover:
            return
        if self._peeking:
            self._peek_tick()            # 熱區規則自己會判斷該不該收
        else:
            self._settle()

    def _peek_tick(self):
        """滑鼠碰到螢幕頂端中央就探頭出來，不必去翻系統匣。"""
        if self._greeting:
            return                       # 打招呼期間不受游標影響
        if self._menu_open():
            return                       # 選單開著，游標當然會離開熱區
        if VISUAL[self.state][2]:
            return                       # 本來就在畫面上，不干涉

        x, y = cursor_pos()
        target = target_screen(self.cfg)
        scr = target.geometry()
        in_zone = (abs(x - scr.center().x())
                   <= peek_half_w(scr.width(), target.devicePixelRatio())
                   and scr.top() <= y <= scr.top() + PEEK_EDGE_PX)

        if not in_zone:
            self._peek_locked = False    # 離開熱區才解鎖，避免喝完立刻又彈回來

        if in_zone and not self._peeking and not self._peek_locked:
            self._peeking = True
            self._refresh_message()
            self._target_reveal(1.0)
            self._target_expand(0.0)
        elif self._peeking and not in_zone:
            on_pill = self.pill_rect().adjusted(-10, -10, 10, 10).contains(
                self.mapFromGlobal(QPoint(x, y))
            )
            if not on_pill:
                self._peeking = False
                self._target_content(0.0)
                self._target_expand(0.0)
                self._target_reveal(0.0)

    def _settle(self):
        """展開停留結束。喝完就滑走消失，其餘縮到各自的停留尺寸。"""
        if self._menu_open():
            return                       # 選單關掉時 _menu_dismissed() 會補做
        if self.state == SATISFIED:
            self._peek_locked = True     # 剛喝完，滑鼠還停在島上，別馬上又探頭
            self._enter(NORMAL)
            return
        if self._hover:
            return
        rest = VISUAL[self.state][1]
        if rest < 0.62:
            self._target_content(0.0)            # 字先走
        self._target_expand(rest)

    # ------------------------------------------------------------ 計時主迴圈

    def _dismiss_if_done(self):
        """已經達標卻還在提醒，就收掉。回傳有沒有真的收。

        這條規則只能有一份實作，而且要放在所有路徑的共同出口。
        第一版寫在 apply_config 裡，只蓋到「在設定裡把目標調低」那一條路，
        漏掉了更常見的一條：狀態會跨重啟保存，所以島一旦卡在
        「還是沒喝喔」配「今天 7/7 次」，每次開機都會把那個狀態原封接回來，
        重開程式等於把同一個 bug 重建一次（使用者實測「沒有改善」就是這樣）。

        現在 tick() 的達標守門會叫它，而 tick 每 5 秒跑一次、任何進入方式
        （重啟接回、改設定、換日）之後都會經過，所以不管怎麼卡進去都出得來。

        不閃「今天達標了」：那句是給「喝完最後一次」用的，
        這些路徑上使用者並沒有喝水。安靜滑走就好。
        """
        if self.state in REMINDING and \
                self.drinks >= self.cfg["daily_target_drinks"]:
            self._enter(NORMAL)
            self._persist()          # 別讓下次啟動又接回這個狀態
            return True
        return False

    def tick(self):
        now = datetime.now()

        today = day_key(now, settings.DAY_ROLLOVER_HOUR)
        if today != self.day:
            self.day = today
            self.drinks = 0
            self.active_s = 0.0
            self.interval_s = self._roll_interval()
            log_event(self.day, "day_start", target=self.cfg["daily_target_drinks"])
            self._persist()
            self._refresh_streak()      # 昨天結算完，連續天數要跟著更新
            self._enter(NORMAL)

        if self.paused_until:
            if now < self.paused_until:
                return
            self.paused_until = None
            log_event(self.day, "resume")
            self._sync_tray()

        if self._peeking and self.state == NORMAL:
            self._refresh_message()               # 探頭時倒數要跟著走
            self.update()

        if self.drinks >= self.cfg["daily_target_drinks"]:
            # 達標，今天不再出現。收掉之後才 return。
            # 這個 return 只擋「不再發新的提醒」，擋不掉已經在畫面上的那一個，
            # 所以要在這裡收——它是所有路徑的共同出口。
            self._dismiss_if_done()
            return

        # 離開電腦不計時：提醒發在你不能行動的時候，只會訓練出無視的反射。
        if idle_seconds() >= self.cfg["idle_threshold_min"] * 60:
            return
        self.active_s += self.cfg["tick_seconds"]

        # 每分鐘落檔一次，程式意外結束最多只丟一分鐘的累積
        self._persist_countdown += 1
        if self._persist_countdown >= max(1, int(60 / self.cfg["tick_seconds"])):
            self._persist_countdown = 0
            self._persist()

        weak_at = self.interval_s + self.cfg["escalate_weak_min"] * 60
        collapse_at = self.interval_s + self.cfg["escalate_collapsed_min"] * 60

        if self.state in (NORMAL, SATISFIED):
            if self.active_s >= self.interval_s:
                log_event(self.day, "remind", drinks=self.drinks)
                self._enter(THIRSTY)
        elif self.state == THIRSTY and self.active_s >= weak_at:
            log_event(self.day, "weak")
            self._enter(WEAK)
        elif self.state == WEAK and self.active_s >= collapse_at:
            log_event(self.day, "collapse")
            self._enter(COLLAPSED)

    # ------------------------------------------------------------ 動作

    def practice(self, on_done=None):
        """引導的最後一步：在真的島上點一次。不計數、不落檔。

        為什麼不用引導視窗裡那台縮小螢幕：那張圖再像也是一張圖，而這一步要練的是
        「把游標移到螢幕上緣那顆藥丸、按下去」這個動作。位置是這個動作的一半，
        在別的地方點一百次也不會記得它其實在螢幕頂端。

        `_practicing` 只有一個作用：讓 drink() 走一條不寫入任何東西的路。
        """
        self._practicing = True
        self._practice_cb = on_done
        # 指令寫在這裡，不寫在引導視窗裡。視窗在螢幕正中央、島在最上緣，
        # 使用者按下去之前最後看到的字是這一句；寫在視窗裡等於寫在他沒在看的
        # 地方，而且兩邊都寫會變成兩個指令搶同一個動作。
        # copy-style: off
        self._enter(THIRSTY, message="點我一下", sub="這次不會算進今天的次數")
        # copy-style: on

    def drink(self):
        """點一下＝「我剛補了水」，不管喝了幾口。不宣稱喝滿一杯，就沒有虛報的壓力。"""
        if self._practicing:
            # 練習不留任何痕跡：不加次數、不重擲間隔、不寫 events、不存檔。
            # 這條路徑必須放在最前面——底下每一行都有副作用。
            self._practicing = False
            # copy-style: off
            self._enter(SATISFIED, message="就是這樣", sub="時間到我會自己出現")
            # copy-style: on
            cb, self._practice_cb = self._practice_cb, None
            if cb:
                cb()
            return

        # 手滑點兩下不能記兩次。
        #
        # 使用者回報：「可以重置計算嗎，不小心一次點了兩次之類的」。他要的是
        # 撤銷，但該修的是別讓它記到兩次——喝完之後島還會亮
        # satisfied_flash_seconds 的確認訊息、繼續掛在畫面上、繼續可以點，
        # 手滑的窗口是敞開的。系統匣圖示的左鍵也是同一條路。
        #
        # 用「距離上次補水多久」判，不要用「島現在是不是 SATISFIED」。
        # 後者看起來更省（狀態本來就在），但它把輸入處理綁在動畫狀態機上：
        # 狀態萬一沒被收掉，補水就永遠記不進去——那比記兩次嚴重得多，
        # 因為記兩次看得見，記不進去是無聲的。時間戳不會卡住。
        #
        # 門檻直接用確認訊息的顯示長度，不另外訂常數：確認還在畫面上的期間，
        # 你才剛看到「喝了，還剩 N 次」，這時候的第二下不可能是故意的。
        now = time.perf_counter()
        if now - self._last_drink_at < self.cfg["satisfied_flash_seconds"]:
            return
        self._last_drink_at = now

        responded = self.state in REMINDING
        log_event(
            self.day, "drink",
            from_state=self.state,
            responded=responded,
            wait_active_s=int(max(0.0, self.active_s - self.interval_s)) if responded else 0,
            drinks=self.drinks + 1,
            target=self.cfg["daily_target_drinks"],
        )
        self.drinks += 1
        self.active_s = 0.0
        self.interval_s = self._roll_interval()
        self._persist()

        target = self.cfg["daily_target_drinks"]
        if self.drinks >= target:
            # 達標的瞬間連續會 +1，這裡是唯一的回饋時機，數字要當場更新
            self._refresh_streak()
            sub = f"連續 {self.streak} 天" if self.streak else None
            self._enter(SATISFIED, message="今天達標了", sub=sub)
        else:
            self._enter(SATISFIED, message=f"喝了，還剩 {target - self.drinks} 次")

    def pause_2h(self):
        self.paused_until = datetime.now() + timedelta(hours=2)
        log_event(self.day, "pause", until=self.paused_until.isoformat(timespec="seconds"))
        self._persist()
        self._enter(NORMAL)

    def show_stats(self, on_settings=False):
        try:
            import stats_window
            # 留著參考，不然視窗會被 GC 掉
            self._stats_win = stats_window.open_window(
                self.cfg, EVENTS_PATH, getattr(self, "_stats_win", None),
                on_config=self.apply_config, on_settings=on_settings,
                on_replay=self.show_onboarding)
        except Exception as exc:                  # 紀錄視窗掛了不該影響提醒本身
            box = QMessageBox()
            box.setWindowTitle("開不了紀錄")
            box.setText(f"開啟紀錄視窗時出錯：\n{exc}")
            box.setIcon(QMessageBox.NoIcon)
            box.exec()

    def show_settings(self):
        self.show_stats(on_settings=True)

    def show_onboarding(self, first_run=False):
        """開首次啟動的引導。從設定的「重看使用說明」也走這條。

        `on_practice` 讓引導的最後一步驅動真的島：那一步要練的是
        「把游標移到螢幕上緣、按下去」，位置是這個動作的一半，在引導視窗裡
        點一張圖練不到。
        """
        import onboard
        self._onboard_win = onboard.open_window(
            lambda result: self._onboarding_done(result, first_run),
            on_practice=self.practice,
            # 帶現有設定進去當起始值。重看使用說明的人若看到一組跟自己無關的
            # 數字、按完「開始」就會把作息洗成別人的。
            wake=self.cfg.get("day_rollover_hour",
                              settings.DEFAULTS["day_rollover_hour"]),
            bedtime=self.cfg.get("bedtime_hour",
                                 settings.DEFAULTS["bedtime_hour"]))

    def _onboarding_done(self, result, first_run):
        """引導按下「開始」之後：存設定、標記已引導，然後安靜地結束。"""
        settings.set_autostart(result["autostart"])
        for key in ("day_rollover_hour", "wake_manual",
                    "bedtime_hour", "bedtime_manual"):
            self.cfg[key] = result[key]
        # 深夜起點是就寢時間的導出值，作息一改就要重算。不重算的話它會停在
        # 引導之前用回退值算出來的那個數字——而使用者剛剛才親口否定了它。
        self.cfg["late_night_start_hour"] = settings.late_start_from_bedtime(
            self.cfg["bedtime_hour"])
        self.cfg["onboarded"] = True
        self.cfg["greeted_version"] = settings.VERSION
        settings.save_config(self.cfg)
        if first_run:
            log_event(self.day, "onboarded")
        # 引導完就不打招呼了。greet() 存在的理由是「使用者不知道它在不在」，
        # 但他剛剛才在最後一頁點過真的島，那個前提已經不成立；剛認識完又滑出來
        # 說「嗨」是多的。
        #
        # 而且「什麼都沒發生」正好是這個工具的承諾：平常它不出現。
        # 引導的最後一幕就是它安靜地消失，那比再演一次還準確。

    def quit_app(self):
        log_event(self.day, "quit", drinks=self.drinks)
        self._persist()
        QApplication.quit()

    def _restore_timing(self, saved, same_day, now):
        """接回上次的計時，接不回就重新開始。

        距上次存檔超過 12 小時就當作新的一段（睡了一覺、或電腦關了一整天），
        不把昨天的累積算進來。
        """
        if same_day:
            try:
                gap = (now - datetime.fromisoformat(saved["saved_ts"])).total_seconds()
            except (KeyError, TypeError, ValueError):
                gap = None
            if gap is not None and 0 <= gap < 12 * 3600:
                self.active_s = float(saved.get("active_s", 0.0))
                self.interval_s = float(saved.get("interval_s", 0.0)) or self._roll_interval()
                # 接回上次的狀態。SATISFIED 是「剛喝完的閃爍」那個過場，
                # 不是一個該被還原的狀態——重開之後停在它會讓島卡在確認訊息上。
                st = saved.get("state")
                if st in (THIRSTY, WEAK, COLLAPSED):
                    self._restored_state = st
                pu = saved.get("paused_until")
                if pu:
                    try:
                        resume_at = datetime.fromisoformat(pu)
                        if resume_at > now:
                            self.paused_until = resume_at
                    except ValueError:
                        pass
                return

        self.active_s = 0.0
        self.interval_s = self._roll_interval()

    def _persist(self):
        save_state({
            "day": self.day,
            "drinks": self.drinks,
            "active_s": round(self.active_s, 1),
            "interval_s": round(self.interval_s, 1),
            "paused_until": self.paused_until.isoformat(timespec="seconds") if self.paused_until else None,
            # 狀態也要存。不存的話，重開之後一律從 NORMAL 起算，而 active_s 已經
            # 超過間隔，於是 tick() 立刻再發一次提醒——每次重開都多念一遍。
            # 那不只煩：多出來的 remind 事件會混進活動紀錄，
            # 把作息推導用的安靜段填掉（實測三筆就讓推導直接回 None）。
            "state": self.state,
            "saved_ts": datetime.now().isoformat(timespec="seconds"),
        })

    # ------------------------------------------------------------ 互動

    def enterEvent(self, event):
        self._hover = True
        if VISUAL[self.state][2] or self._peeking:
            self._target_expand(1.0)
            self._target_content(1.0, delay_ms=60)

    def leaveEvent(self, event):
        self._hover = False
        if not self.hold_timer.isActive():
            self._settle()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 先給觸碰回饋再做事：介面必須立刻承認你按到了
            self.sp_pulse.value = 0.955
            self.sp_pulse.velocity = 0.0
            self.sp_pulse.target = 1.0
            self._kick()
            self.drink()

    def contextMenuEvent(self, event):
        self._popup_menu(event.globalPos())

    # ------------------------------------------------------------ 幾何

    def _stable_h(self):
        """沒有被擠壓、也不會過衝的藥丸高度。

        真正的高度在動畫尾端會繞著目標值抖，任何「跨過門檻就換東西」的判斷
        都得用這個值，否則會像格距那樣反覆切換。
        """
        return lerp(PILL_MIN[1], PILL_MAX[1], clamp(self.sp_expand.value, 0.0, 1.0))

    def _metrics(self, c):
        """內容自己的尺寸。pill_rect 與 _layout 共用同一份，兩邊各算一次就會對不上。"""
        target = self.cfg["daily_target_drinks"]
        pr = lerp(2.6, 3.4, c)
        gap = lerp(7.0, 11.0, c)
        face_gap = lerp(10.0, 16.0, c)

        # 杯子有兩個原生尺寸，塞不下才退成只畫臉——挑哪一個由 pixelface 決定。
        stable_h = self._stable_h()
        cup_cell = pixelface.cup_cell_for(stable_h)
        if cup_cell:
            w, h = pixelface.cup_size(cup_cell)
        else:
            w, h = pixelface.face_size(pixelface.PEEK_CELL)

        # 杯子是矩形，離圓角太近會看起來突出去；臉小得多，貼著 0.25 的內距就好。
        inset = max(stable_h * 0.25, 14.0 if cup_cell else 0.0)
        block_w = w + face_gap + gap * (target - 1) + pr * 2
        return {"w": w, "h": h, "cup_cell": cup_cell, "inset": inset,
                "block_w": block_w, "pr": pr, "gap": gap}

    def pill_rect(self):
        t = clamp(self.sp_expand.value, 0.0, 1.6)
        w = lerp(PILL_MIN[0], PILL_MAX[0], t)
        h = lerp(PILL_MIN[1], PILL_MAX[1], t)

        # 沒有文字時，容器不該比內容寬。
        # 停留尺寸原本是手調的比例（0.35、0.50），那個比例只對「當時的」內容成立：
        # 杯子換小尺寸之後，同樣的 0.35 就在右邊留下一大片空白。
        # 讓寬度直接跟著內容算，停留點改多少都不用再回來調這裡。
        c = clamp(self.sp_content.value, 0.0, 1.0)
        m = self._metrics(c)
        natural = max(m["block_w"] + m["inset"] * 2, PILL_MIN[0])
        w = lerp(min(w, natural), w, c)

        # 擠壓與拉伸：速度快時橫向多撐、縱向補回，
        # 讓形變看起來像有質量的東西在動，而不是一個矩形在改數值。
        squash = clamp(self.sp_expand.velocity * 7.0, -10.0, 16.0)
        w += squash
        h -= squash * 0.22

        pulse = clamp(self.sp_pulse.value, 0.90, 1.05)
        w *= pulse
        h *= pulse

        r = clamp(self.sp_reveal.value, 0.0, 1.2)
        y = PILL_TOP - (1.0 - r) * (PILL_MAX[1] + PILL_TOP + 14)
        return QRectF((WIN_W - w) / 2, y, w, h)

    def _apply_mask(self):
        """只有藥丸本身吃滑鼠事件，其餘讓點擊穿透到底下的視窗。

        遮罩要涵蓋陰影：setMask 同時決定「畫得出來的範圍」與「吃滑鼠的範圍」，
        只留 2px 的話陰影會被整個裁掉。多出來的那圈會吃到滑鼠，但只有幾像素。
        """
        # 遮罩貼著陰影的實際形狀：陰影往下偏，所以上方少留、下方多留。
        # 多留的那圈會吃掉滑鼠事件，在螢幕頂端會擋到別的視窗，不能無腦放大。
        #
        # 一定要 toAlignedRect() 不能 toRect()：toRect() 是四捨五入，藥丸寬度是
        # 小數時（pulse 或內容插值算出來的常態）右緣會少 1px，陰影最外一欄就被裁掉。
        # toAlignedRect() 回傳「包得住這個 QRectF 的最小整數矩形」，才是這裡要的語意。
        self.setMask(self.pill_rect().toAlignedRect().adjusted(
            -PILL_SHADOW - 1, -(PILL_SHADOW - SHADOW_OFFSET_Y) - 1,
            PILL_SHADOW + 1, PILL_SHADOW + SHADOW_OFFSET_Y + 1))

    # ------------------------------------------------------------ 繪製

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)

        rect = self.pill_rect()
        color = QColor(VISUAL[self.state][0])
        c = clamp(self.sp_content.value, 0.0, 1.0)
        radius = rect.height() / 2

        p.setOpacity(clamp(self.sp_reveal.value, 0.0, 1.0))

        # 投影：讓它浮在桌面上而不是貼在上面。
        # 係數是從高斯衰減反推的（見 paintkit），等透明度疊層只會得到硬邊。
        draw_soft_shadow(p, rect, SHADOW_ALPHAS, offset_y=SHADOW_OFFSET_Y)

        # 容器保持中性：垂直漸層給體積，頂緣一道高光模擬上方來的光。
        # 蘋果不用彩色描邊標示狀態，狀態由內容（臉的顏色）承載。
        bg = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        bg.setColorAt(0.0, PILL_TOP_COLOR)
        bg.setColorAt(1.0, PILL_BOTTOM_COLOR)
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(rect, radius, radius)

        hl = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.top() + rect.height() * 0.75)
        hl.setColorAt(0.0, QColor(255, 255, 255, 46))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QBrush(hl), 1.0))
        inner = rect.adjusted(0.5, 0.5, -0.5, -0.5)
        p.drawRoundedRect(inner, inner.height() / 2, inner.height() / 2)

        lay = self._layout(rect, c)
        face = self._draw_face(p, rect, color, lay)

        pips_left = self._draw_pips(p, rect, lay)
        if c > 0.01:
            self._draw_text(p, rect, face, c, pips_left)
        p.setOpacity(1.0)

    def _layout(self, rect, c):
        """算出「臉／杯 + 進度點」這個區塊要擺在哪。

        收合時整個區塊置中，展開時才靠左、進度點推到右緣。
        收合尺寸固定、內容寬度卻隨杯子有無而變，靠左對齊必然在右側留一大片空白——
        置中讓兩種尺寸都不用各自調參數。回傳的東西同時餵給臉與進度點，
        兩者共用同一份計算才不會各算各的而對不齊。
        """
        target = self.cfg["daily_target_drinks"]
        margin = lerp(13.0, 20.0, c)
        m = self._metrics(c)
        w, inset, pr, gap = m["w"], m["inset"], m["pr"], m["gap"]

        face_left = lerp(max(rect.left() + (rect.width() - m["block_w"]) / 2.0,
                             rect.left() + inset),
                         rect.left() + inset, c)
        pips_start = lerp(face_left + w + (m["block_w"] - w - gap * (target - 1) - pr * 2) + pr,
                          rect.right() - margin - pr - gap * (target - 1), c)
        return dict(m, face_left=face_left, pips_start=pips_start)

    def _draw_face(self, p, rect, color, lay):
        """畫角色，回傳它佔用的方框——文字要靠它決定從哪裡開始。

        兩套並存：像素杯（現行）與幾何臉（舊版）。config 的 face_style 切換。
        """
        face_d = rect.height() * 0.60
        inset = rect.height() * 0.25
        cy = rect.top() + rect.height() / 2.0

        if self.cfg.get("face_style", "pixel") == "pixel":
            w, h, cup_cell = lay["w"], lay["h"], lay["cup_cell"]
            cx = lay["face_left"] + w / 2.0
            water = pixelface.WATER_DONE if self.state == SATISFIED else pixelface.WATER
            if cup_cell:
                pixelface.draw_cup(p, cx, cy, clamp(self.sp_level.value, 0.0, 1.0),
                                   self.state, pixelface.GLASS, water, pixelface.INK,
                                   cell=cup_cell)
            else:
                # 探頭時只會是 NORMAL、水位恆滿，杯子本來就沒帶資訊，省下來換臉大一點
                pixelface.draw_at_cell(p, cx - w / 2.0, cy - h / 2.0,
                                       pixelface.PEEK_CELL, self.state, pixelface.INK)
            # 像素關掉抗鋸齒，後面的文字與進度點要自己開回來
            p.setRenderHint(QPainter.Antialiasing, True)
            return QRectF(cx - w / 2.0, cy - h / 2.0, w, h)

        cx = rect.left() + inset + face_d / 2.0

        face = QRectF(cx - face_d / 2.0, cy - face_d / 2.0, face_d, face_d)
        # 臉也給漸層：左上亮、右下暗，看起來像一顆有體積的東西而不是色塊
        fg = QRadialGradient(
            face.center().x() - face_d * 0.24, face.center().y() - face_d * 0.30, face_d * 1.15
        )
        fg.setColorAt(0.0, color.lighter(124))
        fg.setColorAt(0.55, color)
        fg.setColorAt(1.0, color.darker(118))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(fg))
        p.drawEllipse(face)
        self._draw_features(p, face, self.state)
        return face

    def _draw_features(self, p, face, state):
        cx, cy = face.center().x(), face.center().y()
        d = face.width()
        ex, ey = d * 0.20, cy - d * 0.08
        ink = QPen(QColor(28, 28, 28), max(1.4, d * 0.055))
        ink.setCapStyle(Qt.RoundCap)
        p.setPen(ink)
        p.setBrush(Qt.NoBrush)

        if state == COLLAPSED:
            r = d * 0.09
            for sx in (cx - ex, cx + ex):
                p.drawLine(QPoint(int(sx - r), int(ey - r)), QPoint(int(sx + r), int(ey + r)))
                p.drawLine(QPoint(int(sx - r), int(ey + r)), QPoint(int(sx + r), int(ey - r)))
            return

        if state == SATISFIED:
            r = d * 0.10
            for sx in (cx - ex, cx + ex):
                p.drawArc(QRectF(sx - r, ey - r * 0.4, r * 2, r * 1.6), 20 * 16, 140 * 16)
        elif state == WEAK:
            r = d * 0.10
            for sx in (cx - ex, cx + ex):
                p.drawLine(QPoint(int(sx - r), int(ey)), QPoint(int(sx + r), int(ey)))
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(28, 28, 28)))
            r = d * (0.105 if state == THIRSTY else 0.085)
            for sx in (cx - ex, cx + ex):
                p.drawEllipse(QRectF(sx - r, ey - r, r * 2, r * 2))
            p.setPen(ink)
            p.setBrush(Qt.NoBrush)

        my, mw = cy + d * 0.22, d * 0.30
        if state == SATISFIED:
            p.drawArc(QRectF(cx - mw / 2, my - mw * 0.3, mw, mw * 0.8), 200 * 16, 140 * 16)
        elif state == NORMAL:
            p.drawArc(QRectF(cx - mw / 2, my - mw * 0.3, mw, mw * 0.6), 200 * 16, 140 * 16)
        else:
            p.drawLine(QPoint(int(cx - mw / 2), int(my)), QPoint(int(cx + mw / 2), int(my)))

    @staticmethod
    def _make_font(px, weight):
        # 字體改成隨程式散布（見 typeface.py）：以前這裡假設機器上裝了 Noto Sans TC，
        # 那對自用成立，發布出去就不成立，而且要不到時 Qt 是靜默替換的。
        return typeface.make(px, weight)

    @staticmethod
    def _draw_line(p, text, x, center_y, font, color, width):
        """用字體度量算出整數基線再畫。

        走 drawText(QRectF, AlignVCenter) 那條路，基線會落在小數位置，
        灰階抗鋸齒下就是一層糊。直接指定整數基線可以避免。
        順便用 elidedText，訊息太長時是「…」而不是被切一半的字。
        """
        fm = QFontMetrics(font)
        p.setFont(font)
        p.setPen(color)
        shown = fm.elidedText(text, Qt.ElideRight, int(width))
        baseline = int(round(center_y + (fm.ascent() - fm.descent()) / 2.0))
        p.drawText(int(round(x)), baseline, shown)

    def _draw_text(self, p, rect, face, c, pips_left):
        p.save()
        x = face.right() + rect.height() * 0.22
        width = max(40.0, pips_left - 16 - x)     # 文字不能撞到右邊的進度點
        base = p.opacity()
        p.setOpacity(base * c)

        # 動畫中才套位移與縮放——純粹的透明度交叉是「網頁感」，蘋果一定會配上變形。
        # 但靜止時必須把變形歸零：非整數的位移與縮放會讓 Qt 關掉 hinting 改走
        # 變形渲染，字就糊了。移動中糊沒人看得出來，停下來時不行。
        if c < 0.995:
            anchor_y = rect.center().y()
            p.translate((1.0 - c) * -16, anchor_y)
            p.scale(lerp(0.92, 1.0, c), lerp(0.92, 1.0, c))
            p.translate(0, -anchor_y)

        self._draw_line(p, self.message, x, rect.top() + rect.height() * 0.355,
                        self._f_title, INK_PRIMARY, width)
        self._draw_line(p, self.sub_message, x, rect.top() + rect.height() * 0.655,
                        self._f_sub, INK_SECONDARY, width)

        p.setOpacity(base)
        p.restore()

    def _draw_pips(self, p, rect, lay):
        """進度點：永遠垂直置中，對齊臉的中心線，只有水平位置與尺寸隨展開變化。

        三件事：
        1. 一排點從收合位置「移」到展開位置，不是一排淡出、另一排淡入。
           交叉淡入淡出會在中途同時看見兩組點，讀起來像兩個元件在打架。
        2. 垂直永遠置中，所以形變是純水平位移，版面固定是
           「臉 / 文字 / 進度點」三個對齊同一條中心線的區塊。
        3. 沒有文字時，點跟著臉一起置中，不釘在右邊——否則中間一大片空白。

        回傳這排點的左緣，讓文字知道自己能用到哪裡。
        """
        target = self.cfg["daily_target_drinks"]
        pr, gap, start = lay["pr"], lay["gap"], lay["pips_start"]
        py = rect.center().y()

        p.setPen(Qt.NoPen)
        for i in range(target):
            p.setBrush(QBrush(ACCENT if i < self.drinks else QColor(235, 235, 245, 56)))
            p.drawEllipse(QRectF(start + gap * i - pr, py - pr, pr * 2, pr * 2))
        return start - pr

    # ------------------------------------------------------------ 系統匣

    def _build_tray(self):
        tray = QSystemTrayIcon(self)
        tray.setIcon(self._tray_icon())
        # 工具提示必須在 show() 之前設好：Windows 是在圖示註冊當下把提示寫進
        # HKCU\Control Panel\NotifyIconSettings 的，事後才設會留下一筆空白提示，
        # 滑過去什麼都看不到。
        tray.setToolTip(f"{APP_TITLE}　{self._status_sub()}")
        tray.activated.connect(self._tray_clicked)
        # 刻意不設 setContextMenu：右鍵由 _tray_clicked 接手，彈自繪的選單
        tray.show()
        # Windows 11 預設把新圖示摺進「^」，開機自啟時你不會知道它到底有沒有起來。
        tray.showMessage(
            f"{APP_TITLE} 已啟動",
            "系統匣圖示顯示為 pythonw，可拖曳至工作列固定。\n"
            "將游標移至螢幕上緣中央亦可隨時顯示。",
            QSystemTrayIcon.Information, 8000,
        )
        return tray

    def _tray_icon(self):
        pm = QPixmap(32, 32)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        if self.cfg.get("face_style", "pixel") == "pixel":
            water = pixelface.WATER_DONE if self.state == SATISFIED else pixelface.WATER
            pixelface.draw_cup(p, 16, 16, clamp(self.sp_level.value, 0.0, 1.0),
                               self.state, pixelface.GLASS, water, pixelface.INK, cell=2)
        else:
            p.setRenderHint(QPainter.Antialiasing, True)
            color = QColor(VISUAL[self.state][0])
            face = QRectF(3, 3, 26, 26)
            p.setPen(QPen(color.darker(140), 1.2))
            p.setBrush(QBrush(color))
            p.drawEllipse(face)
            self._draw_features(p, face, self.state)
        p.end()
        return QIcon(pm)

    def _sync_tray(self):
        if not hasattr(self, "tray"):
            return
        self.tray.setIcon(self._tray_icon())
        self.tray.setToolTip(f"{APP_TITLE}　{self._status_sub()}")

    def _tray_clicked(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.drink()
        elif reason == QSystemTrayIcon.Context:
            # 系統匣的右鍵選單由我們自己畫（見 menu.py）。
            # QSystemTrayIcon.setContextMenu() 只吃 QMenu，而 QMenu 在 Windows 上
            # 是原生彈出視窗，改不動圓角與陰影——所以不設它，自己接右鍵。
            self._popup_menu(cursor_pos())

    def _menu_head(self):
        """選單頂端那兩行。副標只放標題沒講過的東西。

        第一版把 _status_sub() 整段接在後面，但那個字串本身就含「今天 N/M 次」，
        跟標題完全重複——重複的部分把整行推到爆出容器外。
        副標該回答的是標題沒回答的：喝了多少、下次什麼時候。
        """
        target = self.cfg["daily_target_drinks"]
        title = f"今天 {self.drinks} / {target} 次"

        if self.paused_until:
            return title, f"已暫停，{self.paused_until.strftime('%H:%M')} 恢復"
        est = self.drinks * self.cfg["ml_per_drink_estimate"]
        if self.drinks >= target:
            return title, f"約 {est} cc，今日已達標"
        remain = int(max(0, self.interval_s - self.active_s) // 60)
        when = "即將提醒" if remain <= 0 else f"下次約 {remain} 分後"
        return title, f"約 {est} cc，{when}"

    def _popup_menu(self, pos):
        """選單項目一律用動作或去處來命名。

        「喝了」是口語陳述不是指令；「看喝水紀錄」的「看」是雜訊——
        選單項若是去某個地方，用名詞就夠了；「取消暫停」是雙重否定，
        讀的人要在腦裡繞一圈才知道結果是「會再提醒」。
        「結束」單獨出現有歧義：結束什麼？
        """
        import menu as traymenu

        items = [("記錄補水", self.drink, False)]
        if self.paused_until:
            items.append(("恢復提醒", self._cancel_pause, False))
        else:
            items.append(("暫停提醒 2 小時", self.pause_2h, False))
        items += [("喝水紀錄", self.show_stats, False),
                  ("設定", self.show_settings, False),
                  (None, None, False),
                  ("結束程式", self.quit_app, True)]

        # 留參考，否則彈出視窗會被 GC 掉
        self._menu_ref = traymenu.TrayMenu(self._menu_head(), items)
        self._menu_ref.closed.connect(
            lambda: QTimer.singleShot(0, self._menu_dismissed))
        self._menu_ref.popup_at(QPoint(*pos) if isinstance(pos, tuple) else pos)

    def _cancel_pause(self):
        self.paused_until = None
        log_event(self.day, "resume")
        self._persist()
        self._sync_tray()


# ---------------------------------------------------------------- 統計

def main():
    if not single_instance_guard():
        return 0
    # 舉手：只有走到這裡的本尊可以寫真實的設定、狀態與紀錄。
    # 其他任何人（測試、臨時驗證腳本、互動式 shell）碰到真實路徑一律當場拋例外。
    # 要在 load_config() 之前——設定檔不存在時它會寫一份預設值出去。
    settings.arm_real_writes()
    # 要在舉手之後、其他任何事情之前。從這一行開始，任何沒被接住的例外都會
    # 留下 traceback——在此之前崩潰的話，程式還沒碰到使用者的資料，
    # 而且那種崩潰從 console 跑一次就看得到。
    crashlog.install()
    # 改名的遷移。資料夾那份在 load_config() 裡（它得先搬完才有東西可讀），
    # 自啟這份在這裡——它跟設定檔無關，而且要在使用者有機會去動開關之前做完，
    # 否則面板讀到的是「沒有自啟」，一按就寫了新的，舊的那筆從此沒人管。
    settings._migrate_autostart()
    # 更新之後如果解到新的資料夾，登錄檔還指著舊的那個 exe——設定頁會顯示
    # 自啟是開的，但每天開機拉起來的是舊版。這裡把它改指到現在這支。
    settings.refresh_autostart_path()
    cfg = load_config()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setApplicationDisplayName(APP_TITLE)
    app.setQuitOnLastWindowClosed(False)

    # 要在 QApplication 之後：QFontDatabase 需要 QGuiApplication 才能運作。
    # 失敗不致命（會退到 fallback chain），但設定頁會照實顯示是哪一種情況。
    typeface.ensure_loaded()

    # 主題在這裡先套一次：系統匣選單是島自己彈的，它需要調色盤，
    # 而紀錄視窗要等使用者點開才會被 import。
    import theme
    theme.apply(cfg.get("theme", "auto"))

    # Windows 預設拿「執行檔」的圖示當工作列圖示，也就是 pythonw 的蟒蛇——
    # 這跟系統匣圖示顯示為 pythonw 是同一個根源（見規劃檔）。
    # 宣告自己的 AppUserModelID 之後，工作列與 Alt+Tab 才會改用視窗圖示。
    try:
        # 這個 ID 決定工作列怎麼分組、以及釘選的捷徑指向誰。改名時一起換，
        # 代價是先前釘在工作列上的捷徑會失聯，要重釘一次。
        # 不換的代價比較大：招牌寫 Sipbar，系統認得的身分還是 waterpet，
        # 之後要做通知或跳躍清單就會對不起來。
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("weiimg.sipbar")
    except (AttributeError, OSError):
        pass
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    # 作息會自己觀察（見 settings.infer_schedule），但引導也會問一次——
    # 第一次啟動時紀錄是空的，推導定義上跑不動，只能吃回退值。答過就標記手動。
    # 目標次數由體重推導，除非使用者手動指定過。兩者都在建島之前先算好。
    cfg["daily_target_drinks"] = settings.effective_target(cfg)
    if settings.apply_auto_schedule(cfg, EVENTS_PATH):
        settings.save_config(cfg)

    island = Island(cfg)

    # 啟動時滑下來 4 秒是為了解決「我不知道它在不在、在哪裡」。
    # 對已經知道的人，那是每次開機一次的噪音——所以只在第一次跑、
    # 或版本更新之後才打招呼。用預設行為解掉，不做成設定開關：
    # 每一個設定項都是推給使用者的一個決定。
    if not cfg.get("onboarded"):
        island.show_onboarding(first_run=True)
    elif cfg.get("greeted_version") != settings.VERSION:
        QTimer.singleShot(800, island.greet)
        cfg["greeted_version"] = settings.VERSION
        settings.save_config(cfg)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

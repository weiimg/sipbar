# -*- coding: utf-8 -*-
"""設定：檔案位置、讀寫、推導、開機自啟、資料清除。

設定面板刻意開得很窄。（曾經寫「只有四項」，作息與外觀進來之後那個數字就
不對了。守的是標準，不是數量——數量會變，標準不會。）

篩選標準只有一條：不改就會讓工具對這個人失效。體重（目標差一倍）、
提醒間隔（每個人在電腦前的時間結構不同）、螢幕（多螢幕猜不到）、
開機自啟（沒人會自己去 Startup 資料夾）。其餘全部寫死或自動推導。

刻意不做的東西更重要：沒有「關閉提醒」總開關、沒有「稍後提醒」、
沒有「關掉倒地狀態」、沒有提醒強度調整。這個工具的核心是
「你無法 dismiss 一個狀態」，而設定面板在結構上就是一顆巨大的關閉鍵——
開放什麼就等於允許使用者把它關到失效，然後變成「靜音但沒解除安裝」，
在系統裡躺半年。暫停 2 小時已經是出口，那是唯一一個。

實測支持這個決定：22 次提醒中有 5 次升級到虛弱、2 次到倒地，
七次全部以喝水收場（最快 1 秒、最慢 33 分）。升級機制有效到使用者
根本沒感覺它存在——那不是該給人關掉的東西。

音效（sound_enabled）是這條線上唯一的例外，而且它其實沒有越線：關掉的是
「出聲」這一階，不是升級。島照樣滑下來、照樣變色變大、照樣不自己走，
只是不出聲——少掉一個管道，機制本身完好。「關掉倒地狀態」拿掉的是機制。

它必須有開關，理由跟上面那些相反：聲音會漏出螢幕。畫面上的島只影響正在看
螢幕的那個人，一聲提示音會進到會議、錄影、開放式辦公室裡。沒有開關的音效
不是設計原則，是缺陷。
"""

import json
import math
import os
import shutil
import sys
from datetime import datetime, timedelta

from motion import clamp

# 還在 beta：功能齊了，但只在一台機器上跑過、只有一個使用者的資料。
# 1.0 要等別人裝過、而且撐過 14 天檢核再說。
#
# 改這個字串會讓程式在下次啟動時打一次招呼（滑下來 4 秒），那是刻意的——
# 版本換了就值得說一聲。見 island.main() 的 greeted_version。
VERSION = "0.11.0-beta"

APP_NAME = "Sipbar"
APP_TITLE = "Sipbar"

# 回報問題的去處。設定頁的「回報問題」開這個。
# 放這裡而不是寫死在 stats_window：改網址是身分層級的事，跟版本號、程式名字
# 同一類，不該散在畫面的程式碼裡。
ISSUES_URL = "https://github.com/weiimg/sipbar/issues"

# 一天的分界。訂死，不推導。
#
# 這個值以前是從「習慣起床時間」來的，理由是「你還在電腦前就代表還沒睡，
# 那就還是同一天」。那句話只成立在一個方向——**醒得比平常早就整個壞掉**：
# 起床時間設 10 點的話，你 8 點起來工作，那兩小時全部算前一天，而前一天
# 如果已經達標，島整個早上不會出聲。
#
# 試過讓它學：從活動紀錄找最長的安靜段，取中點當分界。不做的理由有兩層——
# 表層是 infer_wake_hour() 自己的 docstring 就寫著「連續段偵測對雜訊很敏感」
# （幾筆多餘的事件就能讓它縮短或直接回 None）；深層是即使推得準，
# 這個工具的資料量本來就不足以支撐一個會浮動的日界線。
# **一個學不準的機制比一個誠實訂死的常數更糟。**
#
# 5 點是原本的設計意圖（day_key 的 docstring 一直是這樣寫的），也是通用的
# 合理值：幾乎沒有人在 5 點活動，而午夜幾乎所有人都還醒著。
# 不用午夜還有一個理由——午夜期限會製造「睡前趕快把水喝完」的壓力，
# 而深夜模式（23:00 起間隔 ×1.44）存在的目的正是要避免睡前灌水。
DAY_ROLLOVER_HOUR = 5

# 改名前叫 WaterPet。留著這個常數不是為了相容，是為了遷移——
# 資料夾、開機自啟的登錄值都用舊名字建過，直接改名會讓使用者的設定與紀錄
# 變成孤兒：程式開開心心建一個空的新資料夾，而他兩週的紀錄還躺在舊的那個
# 裡面，沒有任何錯誤訊息。
#
# 所以不是「留著兩個名字並存」，是搬完就只剩一個。搬的動作在
# _migrate_data_dir() 與 _migrate_autostart()，兩個都只在還沒搬過時做一次。
OLD_APP_NAME = "WaterPet"

# 設定檔跟著資料走，不放在程式旁邊。
# 打包成 exe 裝進 Program Files 之後那個目錄不可寫，寫入會靜默失敗——
# 使用者改了設定、按了儲存、什麼錯誤都沒有，重開之後全部復原。
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
EVENTS_PATH = os.path.join(DATA_DIR, "events.jsonl")

# 打包成 exe 之後，「隨附的資源在哪」跟「程式本體在哪」是兩個不同的位置，
# 從原始碼跑的時候它們才剛好重疊。兩個都用 __file__ 推的話，凍結之後哪個都不對：
# PyInstaller 會把模組解到一個暫存目錄，__file__ 指的是那裡。
#
# resource_dir()：字體與圖示。凍結時是 sys._MEIPASS（onefile 是暫存區、
#   onedir 是 _internal，兩種模式 PyInstaller 都會設這個值）。
# program_dir()：exe 本體旁邊。使用者眼中「程式在哪」就是這裡，
#   舊版設定檔的偵測要看這裡，看暫存區永遠是空的。


def resource_dir():
    """隨程式散布的資源（assets/）的根目錄。"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def program_dir():
    """程式本體所在的目錄。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = program_dir()
LEGACY_CONFIG_PATH = os.path.join(APP_DIR, "config.json")


# ---------------------------------------------------------------- 誤寫防線
#
# 只有真的程式可以寫真實的資料檔。其餘一律當場拋例外。
#
# 為什麼需要這條：設定頁的 _emit() 會 save_config()，而任何腳本只要開了設定
# 視窗、動到任何一個控制項，就會把使用者調好的設定整份覆蓋掉——沒有錯誤訊息，
# 沒有任何徵兆，下次啟動才發現值全變了。
#
# 這件事發生過兩次。第一次之後在 tests/test_settings.py 開頭寫了一大段註解
# 提醒後人要先把路徑指到沙箱；第二次是讀過那段註解的人照樣踩下去，
# 用一支臨時的驗證腳本把使用者的設定洗成預設值（起床、主題、升級門檻、
# 抖動、深夜倍數、連「已完成引導」都被打回 false）。
#
# 結論很清楚：寫在註解裡的規則擋不住任何人。防線要在程式裡，
# 而且要響——安靜的失敗正是這個 bug 之所以能發生兩次的原因。
#
# 判斷方式刻意不用啟發式（不看有沒有 QT_QPA_PLATFORM、不猜檔名）：
#   - 真的程式在 island.main() 裡呼叫 arm_real_writes()，等於舉手說「我是本尊」
#   - 測試把路徑指到沙箱，寫的就不是真實檔案，本來就放行
#   - 兩者皆非 = 有人在真實資料上跑實驗，攔下來
# 舊資料夾也一起護著。改名之後它還躺在硬碟上（遷移是複製不是搬移），
# 那裡面是使用者唯一一份「改名前」的紀錄——防線沒有理由只保護新的那份。
_OLD_DATA_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), OLD_APP_NAME)
_REAL_PATHS = frozenset(
    os.path.normcase(os.path.abspath(p))
    for p in (CONFIG_PATH, STATE_PATH, EVENTS_PATH,
              # crash.log 也要在防線內。它不像另外三個那樣攸關使用者的紀錄，
              # 但沒列進來的話，任何測試或臨時腳本只要走到 crashlog.record()
              # 就會往使用者真實的資料夾 append，而「防線沒有攔截到任何寫入」
              # 那條斷言照樣回報 []——防線在那條路上是瞎的。
              os.path.join(DATA_DIR, "crash.log"),
              os.path.join(_OLD_DATA_DIR, "config.json"),
              os.path.join(_OLD_DATA_DIR, "state.json"),
              os.path.join(_OLD_DATA_DIR, "events.jsonl")))   # 先凍結，後面誰改路徑都不影響

_real_writes_armed = False
_real_write_violations = []


def real_write_violations():
    """防線攔下來的路徑清單。測試最後斷言它是空的。

    為什麼需要這個：Qt 會吞掉 slot 裡拋出的例外——它把 traceback 印到
    stderr 然後讓程式繼續跑。對盯著畫面的人來說夠明顯，但自動化跑完只會看到
    「全部通過」，而它其實闖進了真實資料。計數器把印出來的 traceback
    變成一條可以斷言的事實。
    """
    return list(_real_write_violations)


def arm_real_writes():
    """宣告「我是真的程式」。只該由 island.main() 呼叫一次。

    測試不要呼叫這個來繞過防線——要寫檔就把路徑指到沙箱，
    那才是正確的做法（見 tests/test_settings.py 開頭）。
    """
    global _real_writes_armed
    _real_writes_armed = True


def guard_real_write(path):
    """要寫真實資料檔又沒舉過手，就在這裡炸掉。

    刻意拋例外而不是靜靜跳過：跳過的話腳本會以為自己存好了，
    而使用者的檔案雖然保住，行為卻跟預期不同——那是換一種說謊方式。
    """
    if _real_writes_armed:
        return
    if os.path.normcase(os.path.abspath(path)) not in _REAL_PATHS:
        return
    _real_write_violations.append(path)
    raise RuntimeError(
        f"擋下對真實資料檔的寫入：{path}\n"
        "只有 island.main() 啟動的本尊可以寫這裡。\n"
        "測試或腳本要寫檔的話，先把 settings.DATA_DIR / CONFIG_PATH / "
        "STATE_PATH / EVENTS_PATH（以及 island 那三個同名的模組層級變數）"
        "指到暫存資料夾，範例見 tests/test_settings.py 開頭的沙箱段落。")

DEFAULTS = {
    # --- 面板上的四項 ---
    "weight_kg": None,              # 留空就用 daily_target_drinks 的預設
    "daily_target_drinks": 7,       # 有效值；由體重推導或手動覆寫，其餘程式一律讀這個
    "target_manual": False,         # True = 使用者手動指定過，體重不再覆蓋它
    # 75 而不是規劃文件算出來的 70：面板上的選項是 30/45/60/75/90，
    # 預設值必須是其中之一，否則分段控制項一打開就顯示「最接近的那個」，
    # 使用者什麼都沒改，設定卻已經跟實際值不一樣。
    # 7 次 × 75 分 = 8.75 小時，一樣鋪得滿一個工作日的電腦時間。
    "interval_min": 75,
    "screen_name": None,            # QScreen.name()，找不到就退回主螢幕
    # 開機自啟不存在這裡：登錄檔才是唯一事實來源，存兩份一定會不同步

    # 習慣起床時間。**這個值不再是換日點**——換日固定在 DAY_ROLLOVER_HOUR，
    # 理由見那裡。它也不再決定夜間模式什麼時候結束（那一端改綁換日那個常數，
    # 理由見 island._is_late）。
    #
    # 剩下的職責只有一個：當作作息推導的基準。就寢時間沒有手動指定時，
    # 它由 infer_bedtime(events, wake) 推出來，而資料不足時的回退值是
    # 「起床往前推 8 小時」——那個 8 小時的假設就掛在這個值上。
    #
    # 鍵名沿用 day_rollover_hour 是因為改名要處理遷移，而它已經存在使用者的
    # config.json 裡。名字現在對不上職責，這是已知的債。
    #
    # **它不在設定面板上，也不在引導裡問。** 面板的篩選標準是「不改就會讓工具
    # 對這個人失效」，而它現在唯一的下游（就寢時間）自己就是一個可以直接設的
    # 值——問兩個值去推一個值，而那個值本來就問得到，是多餘的一題。
    # 所以它一律由活動紀錄推導，沒有手動旗標。
    "day_rollover_hour": 8,

    # 預計就寢時間。問這個而不是問「深夜幾點開始放慢」，理由跟上面問起床
    # 而不問換日完全相同：後者是系統概念，使用者得自己反推（「我三點睡，
    # 減三小時，所以填 0 點」）；就寢時間是他本來就知道的事實。
    # 深夜起點由它減 LATE_BEFORE_SLEEP_H 算出來，不再是獨立的設定值。
    "bedtime_hour": 0,
    "bedtime_manual": False,

    # --- 自動推導，使用者不用回答 ---
    "auto_schedule": True,
    # 由 bedtime_hour 導出，不要直接改這個——改了下次啟動就會被重算蓋掉。
    "late_night_start_hour": 21,

    # "auto" 跟隨系統，其餘 "light" / "dark"
    "theme": "auto",

    # 升級時出聲。**不是「關閉提醒」總開關**——關掉只是讓聲音那一階消失，
    # 島照樣滑下來、照樣升級、照樣不自己走。完整的理由見模組開頭。
    #
    # 預設開著。它只在被忽略 15 分鐘之後才響，平常完全安靜，所以預設開著的
    # 代價很小；反過來預設關掉的話這個功能等於不存在——沒有人會為了一個
    # 自己沒體驗過的東西去翻設定。
    "sound_enabled": True,

    # 自訂音效**當初挑的檔名**，純粹拿來顯示在設定頁上。
    #
    # 真正決定播什麼的是 %LOCALAPPDATA%\Sipbar\sound\ 裡有沒有那個檔案，
    # 這兩個值跟播放完全無關——刪掉、對不上、或使用者手動改過都不影響行為，
    # 最多是那一列顯示「自訂」而不是原本的檔名。
    #
    # 用兩個平的字串而不是一個 dict：DEFAULTS 是用 dict() 淺複製出去的，
    # 巢狀的可變值會被所有人共用，改一個人的設定就改到預設值本身。
    "sound_name_weak": "",
    "sound_name_collapsed": "",

    # 啟動後向 GitHub 查一次有沒有新版。**只查，不下載也不安裝**，
    # 理由見 updates.py 的模組開頭。
    #
    # 預設開著：攜帶版沒有安裝程式，關掉的話使用者永遠不會知道修正發布了，
    # 而這個工具目前每一版都在修「安靜失敗」那類 bug。
    "check_updates": True,

    # --- 寫死，不上面板 ---
    # 單位是「補水次數」不是「杯」：被提醒時你只會喝幾口，用「杯」當單位會逼你
    # 虛報、或因為「才喝兩口」而不敢按——兩種都會讓數字失真。
    "ml_per_drink_estimate": 200,   # 僅供統計顯示，會標明是估算
    # 抖動改成比例：固定 ±10 分在間隔 70 分時合理，設成 30 分就太大了。
    "interval_jitter_pct": 15,
    # 深夜間隔是主間隔的倍數，不是獨立參數——兩個各自可調只會調到互相矛盾。
    "late_night_ratio": 1.45,
    # 幾分鐘沒動鍵鼠算「離開電腦」。15 分對設計師／工程師的工作型態太短：
    # 看素材、讀長文件、開會聽人講話都是「人在、能行動、但不會碰鍵鼠」，
    # 而這些活動通常持續 10–40 分鐘，會整段被判成離開、整段不計時。
    # 真正的離開反而落在兩端：上廁所 5 分鐘內（無所謂），午餐開會超過 30 分。
    # 中間有個天然的縫，門檻放在縫上。
    # 代價也不對稱：判錯「離開」最多多算一個門檻的時間（有上界），
    # 判錯「在」會讓整段活動都不計時（沒有上界，可能是好幾小時）。
    "idle_threshold_min": 30,
    "escalate_weak_min": 15,
    "escalate_collapsed_min": 40,
    "tick_seconds": 5,
    "thirsty_hold_seconds": 6,
    "weak_hold_seconds": 8,
    "satisfied_flash_seconds": 1.8,
    "face_style": "pixel",

    # 首次啟動的引導跑過沒有。跟 greeted_version 是兩件事：
    # 引導是一次性的教學，打招呼是每次改版提醒使用者「它還在」。
    "onboarded": False,

    # 第一次達標時提示過「右鍵可以看紀錄」沒有。
    #
    # 紀錄視窗有連續天數、熱圖、成就，做得比島本身還完整，而唯一的入口是
    # 右鍵——一個沒有任何視覺提示的動作。第一次達標是這句話最該出現的時刻：
    # 使用者第一次真的有東西可看，而且他正盯著島。
    #
    # 只講一次。講第二次就變成他每天都要略過一次的東西，而那正是這個工具
    # 最不想變成的樣子。一個布林值就夠，不需要遷移。
    "records_hinted": False,

    # --- 內部狀態 ---
    # 啟動時滑下來 4 秒是為了解決「我不知道它在不在」，對已經知道的人是每天一次的
    # 噪音。用預設行為解掉，不做成開關——每個設定項都是推給使用者的一個決定。
    "greeted_version": None,
}

TARGET_MIN, TARGET_MAX = 4, 12
INTERVAL_CHOICES = (30, 45, 60, 75, 90)

# 值一定得是數字的那些鍵。
#
# 從 DEFAULTS 自己推導，不另外手抄一份清單：抄的話，以後新增數字設定的人得
# 記得回來補一行，而漏掉的那一個不會有任何徵兆——它正是這條防線要擋的東西。
# bool 要排除（它是 int 的子類別，理由見 `_as_number()`）；weight_kg 要手動
# 補（預設是 None＝沒填，從型別看不出它是數字），它也是唯一一個「讀不出來
# 就當作沒填」而不是退回預設值的欄位。
NUMERIC_KEYS = frozenset(
    {k for k, v in DEFAULTS.items()
     if isinstance(v, (int, float)) and not isinstance(v, bool)}
    | {"weight_kg"})

# 值只能是真假的那些鍵。JSON 有真正的 true / false，但手改的人很容易寫成
# 字串，而 **Python 的 `bool("false")` 是 True**——「關掉」被讀成「打開」，
# 而且完全看不出來。音效那一個最糟：它平常本來就安靜，只在提醒被忽略 15 分鐘
# 之後才響，所以「以為關掉了但其實開著」要等到某天開會時才會發現。
BOOL_KEYS = frozenset(k for k, v in DEFAULTS.items() if isinstance(v, bool))

# 認得的寫法。大小寫與前後空白都吃，因為手改的人不會照 JSON 的規矩寫。
_BOOL_WORDS = {"true": True, "yes": True, "on": True, "1": True,
               "false": False, "no": False, "off": False, "0": False}

# 值只能是清單裡那幾個字串的鍵。
#
# theme 特別要擋：`theme.resolve()` 拿它去查一個 dict，餵 list 進去是
# TypeError（unhashable），而 `theme.apply()` 在 island.main() 裡、**建島之前、
# 沒有任何 try**——又是一次「點了圖示什麼都沒發生」。
# 認不得的字串本來就會退回系統配色，那條路沒問題，要擋的是型別。
ENUM_KEYS = {"theme": ("auto", "light", "dark"),
             "face_style": ("pixel", "geometry")}

# 自由字串：螢幕名稱、音效檔名、打過招呼的版本。內容不管（那是使用者的機器上
# 的事實），型別要管——不是字串就退回預設，別讓它流到 os.path.basename()
# 或版本比較那裡。
TEXT_KEYS = frozenset(("screen_name", "sound_name_weak",
                       "sound_name_collapsed", "greeted_version"))


# ---------------------------------------------------------------- 讀寫

DATA_FILES = ("config.json", "state.json", "events.jsonl")


def _migrate_data_dir():
    """改名前的資料夾（%LOCALAPPDATA%\\WaterPet）整份搬過來。回傳搬了幾個檔。

    只在新資料夾還沒有 config.json 時做一次，之後永遠不再碰舊的那個。
    判斷用 config.json 而不是「資料夾存不存在」：資料夾可能被別的路徑先建出來
    （save_state 會 makedirs），那時裡面是空的，用資料夾判斷就會直接跳過遷移，
    使用者的紀錄從此看不到。

    複製不是搬移，跟 _migrate_legacy 同一個理由：舊的留著當備份。萬一遷移
    本身有 bug，原始資料還在原地，不是只剩一份被寫壞的。

    舊資料夾從現在的 DATA_DIR 的同層去推，不寫死絕對路徑——測試把 DATA_DIR
    指到沙箱時，同層的「舊資料夾」自然不存在，遷移就安靜地不做事。
    寫死的話，跑一次測試就會把使用者的真實紀錄複製進沙箱。
    """
    if os.path.exists(CONFIG_PATH):
        return 0
    old = os.path.join(os.path.dirname(DATA_DIR), OLD_APP_NAME)
    if not os.path.isdir(old) or os.path.normcase(old) == os.path.normcase(DATA_DIR):
        return 0
    moved = 0
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        for name in DATA_FILES:
            src = os.path.join(old, name)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(DATA_DIR, name))
                moved += 1
    except OSError:
        return moved
    return moved


def _migrate_legacy():
    """把舊的「程式旁邊的 config.json」搬到資料夾裡。回傳有沒有搬。

    只在新位置還沒有檔案時搬，而且是複製不是移動——舊檔留著當備份，
    使用者若退回舊版程式也不會發現設定憑空消失。
    """
    if os.path.exists(CONFIG_PATH) or not os.path.exists(LEGACY_CONFIG_PATH):
        return False
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        shutil.copy2(LEGACY_CONFIG_PATH, CONFIG_PATH)
        return True
    except OSError:
        return False


# 這一輪被退回預設的欄位。診斷資訊會報出來——設定值被換掉之後畫面上一切正常
# （值是合法的），使用者只會覺得「我明明改了卻沒有用」，而那個疑惑沒有出口。
_repaired = []


def repaired_keys():
    """最近一次讀設定時，有哪些欄位讀不出數字而被退回預設。"""
    return list(_repaired)


def _as_bool(v):
    """設定檔裡的值當成真假讀。讀不出來就回 None（＝當作沒填）。

    真正的 bool 直接收；字串查表（`"false"` / `"no"` / `"0"` 都是假）；
    0 與 1 也收，那是很多人寫開關的習慣。其餘一律讀不出來——
    **特別是 `"maybe"` 這種認不得的字串，不能因為它非空就當成真。**
    """
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return _BOOL_WORDS.get(v.strip().lower())
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(v)
    return None


def sanitize_config(cfg):
    """把設定檔裡每一個數字欄位變回真的數字。就地改，回傳同一個 dict。

    `_as_number()` 原本只套在體重推導那三個入口，因為 0.10.x 修的是「一個引號
    讓程式開不起來」，而當時炸的位置就在那三個。但同一份 `config.json` 裡還有
    十幾個數字欄位一樣改得到——`DESIGN.md` 甚至正在教使用者去改那批沒有上面板
    的值——而後果分成兩種，第二種更難發現：

      - `interval_min`、`late_night_ratio`、`tick_seconds` 加了引號：
        程式開不起來，跟體重那次同一個形狀。
      - `idle_threshold_min`、`escalate_weak_min` 加了引號：
        島活著、畫面正常、倒數照走，但 tick 每一輪都在
        `idle_seconds() >= "30" * 60` 撞上 `float >= str` 而拋例外，
        於是**永遠不再提醒**，而且完全看不出來。

    第二種正是這個專案一直被咬的形狀。

    在這一個地方一次套完，不是在每個讀取點各補一次：讀取點有六十幾個，補到
    第五十個就會漏，而漏掉的那個沒有徵兆。這裡是所有設定值的唯一入口。

    數字之外，布林、列舉（theme / face_style）與自由字串也一起收。三種的失敗
    形狀不同：數字型別不對會拋例外，布林型別不對會**安靜地做相反的事**
    （`bool("false")` 是 True），列舉型別不對又回到拋例外（見 ENUM_KEYS）。

    **修好的值不寫回檔案。** 使用者打錯的那個字元留在原地，他下次打開設定檔
    才看得出自己改了什麼；每次啟動重修一次，代價只是幾十次型別轉換。
    """
    global _repaired
    repaired = []
    for key in sorted(NUMERIC_KEYS):
        if key not in cfg:
            continue
        fallback = DEFAULTS[key]
        n = _as_number(cfg[key])
        # tick_seconds 是唯一一個「0 也不行」的：它直接餵給 QTimer，0 毫秒的
        # 計時器會把一顆核心跑滿，而 active_s 每次加 0，倒數永遠走不完——
        # 又是一次「島活著但不再提醒」。其餘欄位的 0 都有意義（抖動 0＝不抖、
        # 就寢 0 點＝午夜是預設值），不要順手一起擋掉。
        if n is None or (key == "tick_seconds" and n <= 0):
            value = fallback              # weight_kg 的 fallback 就是 None＝沒填
            # 只有「讀不出來」才記一筆。`"45"` 讀得出 45，使用者要的就是 45，
            # 行為跟他預期的一致，沒有需要解釋的東西——把它一起報出去，
            # 只會讓真正被換掉的那幾項淹在雜訊裡。
            if value != cfg[key]:
                repaired.append(key)
        elif isinstance(fallback, float):
            value = float(n)
        else:
            # 預設是整數的欄位收成整數：小時步進器與間隔分段控制項直接拿它去
            # 顯示，8.0 會被印成「8.0 點」。weight_kg 沒有預設值可以參照，
            # 跟著輸入框的驗證器（QIntValidator）走整數。
            value = int(round(n))
        cfg[key] = value

    for key in sorted(BOOL_KEYS):
        if key not in cfg:
            continue
        b = _as_bool(cfg[key])
        if b is None:
            repaired.append(key)
            cfg[key] = DEFAULTS[key]
        else:
            cfg[key] = b            # 讀得懂就照他的意思，"false" 就是關

    for key, allowed in sorted(ENUM_KEYS.items()):
        if key not in cfg:
            continue
        if cfg[key] not in allowed:
            repaired.append(key)
            cfg[key] = DEFAULTS[key]

    for key in sorted(TEXT_KEYS):
        if key not in cfg:
            continue
        # None 是合法的（＝沒設過），其餘只收字串。
        if cfg[key] is not None and not isinstance(cfg[key], str):
            repaired.append(key)
            cfg[key] = DEFAULTS[key]

    # 排序過再交出去：三組（數字、布林、列舉／字串）是分開掃的，不排的話
    # 診斷資訊裡的順序取決於掃描順序，看起來像亂的。
    _repaired = sorted(repaired)
    return cfg


def _upgrade_keys(raw):
    """舊版的鍵名換成新的。使用者調過的值不能因為改版就被丟掉。

    跑在 `sanitize_config()` 後面，所以這裡的值已經是數字了。順序不能反過來：
    底下三條都在對設定值做算術或比較，`"75"` 會讓第一條 TypeError，
    也會讓第三條把 `"7"` 判成「跟預設的 7 不一樣」而誤標成手動指定。
    """
    # 兩個舊鍵不在 DEFAULTS 裡，sanitize_config() 掃不到它們，所以這裡自己
    # 過一次 _as_number()——被丟掉的舊鍵改壞了，不該連累還在用的新鍵。
    base = _as_number(raw.get("interval_min")) or DEFAULTS["interval_min"]
    # interval_jitter_min（固定分鐘）-> interval_jitter_pct（比例）
    if "interval_jitter_min" in raw and "interval_jitter_pct" not in raw:
        old = _as_number(raw["interval_jitter_min"])
        if old is not None:
            raw["interval_jitter_pct"] = int(round(old / base * 100))
    # late_night_interval_min（絕對值）-> late_night_ratio（倍數）
    if "late_night_interval_min" in raw and "late_night_ratio" not in raw:
        old = _as_number(raw["late_night_interval_min"])
        if old is not None:
            raw["late_night_ratio"] = round(old / base, 2)
    # 使用者自己調過目標，升級後不能被體重推導蓋掉
    if "daily_target_drinks" in raw and "target_manual" not in raw:
        raw["target_manual"] = raw["daily_target_drinks"] != DEFAULTS["daily_target_drinks"]
    # 有設定檔就代表這個人已經在用了。引導是給第一次啟動的人看的，
    # 對已經用了兩週的人跳出「桌上現在有水嗎」是搞錯對象。
    # 要重看走設定的「關於」，不要靠升級時彈出來。
    raw.setdefault("onboarded", True)
    # 換算完就把舊鍵刪掉。留著沒有壞處（沒有人讀），但使用者打開設定檔會看到
    # 兩組互相矛盾的值，不知道哪個才算數——發布出去的東西不該讓人猜。
    # wake_manual 在起床時間退出設定面板時一起拿掉了。留著的話它會凍住一個
    # 使用者再也看不到、也改不掉的值：旗標是 True 就永遠不再推導，而畫面上
    # 沒有任何地方能把它關掉。刪掉等於交還給推導，那是現在唯一的來源。
    for dead in ("interval_jitter_min", "late_night_interval_min", "wake_manual"):
        raw.pop(dead, None)
    return raw


def load_config():
    cfg = dict(DEFAULTS)
    # 順序有意義：先把改名前那個資料夾整份接過來，再處理更早期
    # 「config.json 放在程式旁邊」那一版。兩個都只在還沒搬過時做一次。
    _migrate_data_dir()
    _migrate_legacy()
    raw = None
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            pass          # 壞掉的設定檔用預設值頂著，不要讓程式起不來
    else:
        save_config(cfg)
    # 整份不是 JSON 物件時（被改成 null、一個陣列、或只剩一個數字）也一樣頂著。
    # 這個判斷不能省：`_upgrade_keys()` 會對它呼叫 `.setdefault()`，而那是
    # AttributeError，不在上面接住的兩種例外裡——照樣開不起來。
    if isinstance(raw, dict):
        cfg.update(_upgrade_keys(sanitize_config(raw)))
    return cfg


# ---------------------------------------------------------------- 寫入健康狀態
#
# 三個寫使用者資料的函式（save_config、island.save_state、island.log_event）
# 全都是「寫不進去就當作沒事」。那個設計本身是對的——寫檔失敗不該讓程式崩潰，
# 也不該讓補水這個動作停擺。
#
# **但它安靜過頭了。** 2026-08-19 實際發生過：程式活著、島照常提醒、倒數照常走，
# 而補水一次都沒有被記錄，整整 3.5 小時。使用者不會發現，因為畫面上一切正常；
# 他不發現就不會回報，於是這種災情永遠不會有人知道。
#
# 所以失敗要被數出來，並且讓介面說得出口。
#
# 門檻放 3 是因為偶發失敗很常見（防毒或索引服務會在檔案剛寫完時開一個掃描用的
# handle，save_state() 自己就為此重試六次）。狀態每 60 秒落檔一次，所以大約
# 三分鐘存不進去才會出聲，短暫的干擾不會變成狼來了。
WRITE_FAIL_THRESHOLD = 3

# **每個檔案各記一份，不能共用一個計數器。**
#
# 第一版是共用的，任何一次成功就歸零——那讓它偵測不到最可能發生的那種故障。
# events.jsonl 被雲端同步或防毒單獨鎖住時：drink() 是 log_event() 緊接著存檔，
# 記錄失敗的下一行就被存檔的成功抹掉；就算不補水，定期落檔每 60 秒也會抹一次。
# 於是「一整天的補水一筆都沒寫進去」在畫面上完全看不出來，而那正是要修的災情。
#
# 這件事實測過：把 events.jsonl 設成唯讀、其他一切正常，連按十次補水，
# 十筆全部遺失，而計數器從頭到尾是 0、島上顯示「今天已達標」。
#
# 而且 events.jsonl 特別容易單獨失敗：save_state() 會重試六次把暫時性干擾濾掉，
# log_event() 是直接 append、零重試。最脆弱的那個偏偏是共用計數器看不見的。
_write_fail_streaks = {}


def note_write(kind, ok):
    """每次寫使用者資料之後回報成敗。kind 是 config / state / events。"""
    _write_fail_streaks[kind] = 0 if ok else _write_fail_streaks.get(kind, 0) + 1


# 島上那句示警只講「紀錄」，所以只有這兩個檔案該讓它出聲。
#
# **config.json 刻意不算在內**，兩個理由：
#   - 它只在使用者動設定時才寫，沒有任何定期寫入可以把計數歸零。一旦踩到門檻
#     （設定頁的時間步進器滾一下滾輪就送出好幾次存檔，很容易踩到），示警就會
#     掛著一整個 session 不走，還蓋掉「暫停中」與倒數。示警不會消失等於沒有示警：
#     使用者學會無視它，等到真的掉紀錄那天它已經沒有意義了。
#   - 設定存不進去是**看得見的**：下次打開設定頁就會發現值退回去了。
#     而紀錄存不進去完全看不見，那才是這道示警存在的理由。
#
# 它仍然被計數，診斷資訊看得到。
RECORD_FILES = ("state", "events")


def write_trouble():
    """紀錄是不是連續存不進去了。介面拿它決定要不要示警。"""
    return any(_write_fail_streaks.get(k, 0) >= WRITE_FAIL_THRESHOLD
               for k in RECORD_FILES)


def failing_writes():
    """哪些檔案正在連續失敗。診斷資訊要講得出是哪一個，不然回報者只能說
    「紀錄好像不見了」，而那句話沒辦法縮小範圍。"""
    return sorted(k for k, n in _write_fail_streaks.items()
                  if n >= WRITE_FAIL_THRESHOLD)


def write_fail_streak(kind=None):
    """連續失敗幾次。不指定 kind 就回傳最嚴重的那一個。"""
    if kind is not None:
        return _write_fail_streaks.get(kind, 0)
    return max(_write_fail_streaks.values(), default=0)


def save_config(cfg):
    """寫設定。先寫暫存再換檔，中途斷電不會留下半個檔。"""
    guard_real_write(CONFIG_PATH)
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
        note_write("config", True)
        return True
    except OSError:
        note_write("config", False)
        return False


# ---------------------------------------------------------------- 推導

def _as_number(v):
    """設定檔裡的值當成數字讀。讀不出來就回 None（＝當作沒填）。

    **`config.json` 是純文字，使用者改得到**，而說明文件本身就在教人去改它
    （單次水量沒有上面板，想調只能手改）。手改就會有 `"weight_kg": "65"` 這種
    多了引號的情況——JSON 讀進來是字串，`kg * 30` 就變成把字串重複 30 次，
    然後除以 200 當場 TypeError。

    這條例外炸得起來的位置很糟：`effective_target()` 在 `island.main()` 裡、
    **建立動態島之前**被呼叫，那一行沒有任何 try。於是一個引號就讓整個程式
    開不起來，而使用者看到的是「點了圖示什麼都沒發生」——跟程式沒裝好一樣，
    他不會知道問題出在自己改的那個字元上。

    2026-08-19 實際在沙箱重現過：寫一份 `weight_kg` 是字串的設定檔，
    `load_config()` 過得去，下一行就死。

    bool 特別擋掉：Python 的 `True` 是 `int` 的子類別，會被 `float()` 收成 1.0，
    於是「體重 True」變成 1 公斤。那不是使用者的意思，當作沒填才對。

    無限大與 NaN 也擋掉。它們讀得出來（JSON 的 `1e400` 就是 inf，而 Python 的
    json 預設收 `NaN` 這個字面值），但下游全是算術：`int(round(inf))` 是
    OverflowError、`int(round(nan))` 是 ValueError，而 NaN 的每一種比較都回
    False，會讓「離開電腦不計時」那條判斷永遠不成立。讀得出來但算不動的東西
    等於沒填。
    """
    if v is None or isinstance(v, bool):
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def target_from_weight(kg, ml_per_drink=None):
    """體重換算每日補水次數。回傳 None 代表沒填體重。

    體重 × 30cc  = 每日飲品目標，不含食物水分。這個定義要寫對：
                   EFSA 與 IOM 都抓「食物約佔總水分 20%、飲品 80%」，
                   把它讀成「總需求」再往下扣，就會扣兩次。
                   國健署「成人 6–8 杯 × 240ml = 1440–1920cc」講的同樣是喝進去的，
                   跟這一項才是同類；65kg 推出 1950cc，貼在那個區間的上緣。
    × 0.7        = 工具承擔的比例。起床那杯（建議 300–500cc）與三餐湯水
                   發生在它管不到的地方，只算坐在電腦前的部分。
    ÷ 單次的量    = 次數。這個除數以前寫死成 200,是整條公式最大的誤差來源——
                   本檔開頭自己就說「被提醒時你只會喝幾口」,而幾口不是一整杯。
                   除數凍住的時候,使用者把 ml_per_drink_estimate 調成 150,
                   目標次數不會跟著動,於是他實得 7×150=1050cc,
                   而公式的意圖是 1365cc,少 23% 且畫面上完全看不出來。
                   現在它讀同一個設定值,調單次量、次數自己跟著跑。

    65kg：200cc → 7 次（原始設計）、150cc → 9 次。
    """
    kg = _as_number(kg)
    if not kg:
        return None
    ml = _as_number(ml_per_drink) or DEFAULTS["ml_per_drink_estimate"]
    return int(clamp(round(kg * 30 * 0.7 / ml), TARGET_MIN, TARGET_MAX))


def effective_target(cfg):
    """實際要用的每日次數：手動覆寫 > 體重推導 > 預設。

    三個入口值都經過 `_as_number()`。它們全部來自 `config.json`，而這個函式
    在建立動態島之前就會被呼叫，任何一個型別不對都會讓程式開不起來。
    """
    if cfg.get("target_manual"):
        manual = _as_number(cfg.get("daily_target_drinks"))
        return int(clamp(manual or DEFAULTS["daily_target_drinks"],
                         TARGET_MIN, TARGET_MAX))
    return target_from_weight(cfg.get("weight_kg"),
                              cfg.get("ml_per_drink_estimate")) \
        or DEFAULTS["daily_target_drinks"]


def late_night_interval(cfg):
    """深夜間隔＝主間隔 × 倍數。不是獨立參數，避免兩個各自可調而互相矛盾。"""
    return int(round(cfg["interval_min"] * cfg.get("late_night_ratio",
                                                   DEFAULTS["late_night_ratio"])))


# ---------------------------------------------------------------- 作息推導

LOOKBACK_DAYS = 14
MIN_EVENTS = 20            # 少於這個量的樣本，任何推導都只是在放大雜訊
MIN_DAYS = 3               # 中位數至少要這麼多天才有意義
MIN_QUIET_H = 4            # 安靜時段至少要這麼長才算數
QUIET_RATIO = 0.15         # 低於「平均每小時」這個比例就算安靜
LATE_BEFORE_SLEEP_H = 3    # 睡前幾小時開始放慢提醒
MIN_AWAKE_H, MAX_AWAKE_H = 8, 20   # 清醒時段落在這個範圍外，代表推導的前提不成立

# 深夜起點距離起床多久。夾的是推導的結果，不只是輸入。
# 只驗輸入擋不掉壞答案：med 取到合法下界 8 的時候，起點 = 起床 + 5，
# 7 點起床就是中午 12 點進入深夜——一天有 19 小時被當成深夜、提醒全程放慢。
# 而下午外出拍攝、晚上才回到電腦前的接案者，天生就會產生這種輸入。
# 這個起點不在設定面板上，apply_auto_schedule 每次啟動又無條件重算，
# 使用者發現了也改不掉，所以防線只能設在這裡。
LATE_OFFSET_MIN, LATE_OFFSET_MAX = 8, 17

# 只有這些事件代表「人真的在電腦前」。
# day_start / pause / resume / quit 是程式自己的記帳，跟人在不在無關——
# 把它們算進來，換日事件本身就會被當成一天的活動高峰，推導直接自我實現。
# remind / weak / collapse 雖然是程式發的，但 tick() 在閒置時會直接 return，
# 所以它們只在人在的時候才會出現，是有效訊號。
ACTIVITY_EVENTS = ("drink", "remind", "weak", "collapse")


def activity_hours(events_path, lookback_days=LOOKBACK_DAYS):
    """回傳 24 格的活動直方圖：每個小時各發生過幾次活動。"""
    hist = [0] * 24
    if not os.path.exists(events_path):
        return hist
    stamps = []
    try:
        with open(events_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("event") in ACTIVITY_EVENTS and row.get("ts"):
                    try:
                        stamps.append(datetime.fromisoformat(row["ts"]))
                    except ValueError:
                        pass
    except OSError:
        return hist
    if not stamps:
        return hist

    cutoff = max(stamps).timestamp() - lookback_days * 86400
    for s in stamps:
        if s.timestamp() >= cutoff:
            hist[s.hour] += 1
    return hist


def _longest_quiet_run(hist):
    """找出最長的一段「幾乎沒有活動」的連續小時，回傳 (起點, 長度)。

    時刻是環狀的，安靜時段幾乎一定跨過午夜或清晨，所以要繞著找，
    不能只掃 0..23 一遍。
    """
    total = sum(hist)
    if total <= 0:
        return None
    threshold = total / 24.0 * QUIET_RATIO
    quiet = [h <= threshold for h in hist]
    if all(quiet) or not any(quiet):
        return None                     # 整天都安靜或整天都忙，都推不出東西

    best = (None, 0)
    for start in range(24):
        if not quiet[start] or quiet[(start - 1) % 24]:
            continue                    # 只從「安靜段的第一個小時」起算
        length = 0
        while quiet[(start + length) % 24] and length < 24:
            length += 1
        if length > best[1]:
            best = (start, length)
    return best if best[0] is not None else None


def infer_wake_hour(events_path):
    """推導「習慣起床時間」，資料不夠就回 None。

    做法：把活動事件攤成 24 格直方圖，找最長的一段安靜時間，
    取那一段的結束——那是你重新回到電腦前的時刻，也就是起床。

    注意是結束不是開始。安靜段的開始是「你停止用電腦」（≈ 就寢），
    兩者都落在空檔裡，所以都能當換日點用，但語意差很多：
    拿就寢時間當換日，哪天你做過頭做到那個時刻之後，換日會在你還在
    工作時把當天次數歸零。起床時間沒有這個破口。

    這個值只是初始建議。使用者可以在設定裡改，改過就不再被覆蓋——
    連續段偵測對雜訊很敏感（實測三筆多餘的事件就能讓它從 6 小時縮到
    3 小時、直接回 None），不該是唯一的路。
    """
    hist = activity_hours(events_path)
    if sum(hist) < MIN_EVENTS:
        return None
    run = _longest_quiet_run(hist)
    if not run or run[1] < MIN_QUIET_H:
        return None
    return (run[0] + run[1]) % 24


def infer_late_hour(events_path, wake_hour):
    """推導深夜模式起點：每天最後一次活動的中位數，往前推 3 小時。

    「每天」由起床時間定義（一天 = [起床, 起床+24)），所以這個推導
    建立在使用者已經給定的值上，不必再自己猜天的邊界。

    每天最後一次活動 ≈ 你當天收工的時間 ≈ 上床時間。
    往前 3 小時是有依據的：睡前 2–3 小時的攝取才是造成夜間起身的區間，
    那正是這個機制要避開的東西。

    取中位數不取平均：一次特例（熬夜、或程式重啟造成的雜訊事件）
    會把平均拉走，卻撼動不了中位數。實測把一筆離群值拿掉，
    結果從 00:00 變成 23:42，仍然是 00:00。

    資料不足時回退到「起床 − 11 小時」（假設睡 8 小時、睡前 3 小時開始放慢）。
    在真實資料上兩條路徑得出同一個答案，是這個模型沒亂跑的旁證。
    """
    fallback = (wake_hour - 11) % 24
    if not os.path.exists(events_path):
        return fallback

    stamps = []
    try:
        with open(events_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("event") in ACTIVITY_EVENTS and row.get("ts"):
                    try:
                        stamps.append(datetime.fromisoformat(row["ts"]))
                    except ValueError:
                        pass
    except OSError:
        return fallback
    if not stamps:
        return fallback

    # 以起床時間為原點切天，取每天最後一次活動距起床幾小時
    days = {}
    for t in stamps:
        key = (t - timedelta(hours=wake_hour)).date()
        off = (t.hour + t.minute / 60.0 - wake_hour) % 24
        days[key] = max(days.get(key, 0.0), off)
    offsets = sorted(days.values())
    if len(offsets) < MIN_DAYS:
        return fallback

    n = len(offsets)
    med = offsets[n // 2] if n % 2 else (offsets[n // 2 - 1] + offsets[n // 2]) / 2.0

    # 合理範圍的防線。使用者可以把起床時間設在自己實際還在活動的時段裡
    # （例如明明 09:00 就在用電腦卻填 11:00），那時候「一天」的邊界會切在
    # 活動中間，中位數變成 23 小時，往回推 3 小時得出 07:00——完全是垃圾。
    # 沒有人的一天在起床後 3 小時就結束，也沒有人撐到 22 小時。
    # 落在範圍外就代表這個推導的前提不成立，退回從起床時間直接推。
    if not (MIN_AWAKE_H <= med <= MAX_AWAKE_H):
        return fallback
    # 夾住結果。輸入通過上面那關不代表輸出可用——理由寫在 LATE_OFFSET_MIN 那裡。
    offset = clamp(round(med - LATE_BEFORE_SLEEP_H), LATE_OFFSET_MIN, LATE_OFFSET_MAX)
    return int(wake_hour + offset) % 24


def infer_bedtime(events_path, wake_hour):
    """推導就寢時間。就是 infer_late_hour 的另一面——那個函式內部本來就先算出
    就寢時間再往前推 3 小時，這裡只是把中間那個值還原出來給介面用。

    刻意用加回去而不是另寫一份推導：兩份公式一定會漂開，而使用者看到的
    「就寢時間」與程式用的「深夜起點」一旦對不起來，介面就在說謊。
    """
    return (infer_late_hour(events_path, wake_hour) + LATE_BEFORE_SLEEP_H) % 24


def late_start_from_bedtime(bedtime_hour):
    """深夜起點 = 就寢時間往前 LATE_BEFORE_SLEEP_H 小時。

    睡前 2–3 小時的攝取才是造成夜間起身的區間，那正是這個機制要避開的東西。
    """
    return int(bedtime_hour - LATE_BEFORE_SLEEP_H) % 24


def infer_schedule(events_path):
    """兩個都推導，回傳 (起床時間, 深夜模式起點)。資料不夠回 None。"""
    wake = infer_wake_hour(events_path)
    if wake is None:
        return None
    return wake, infer_late_hour(events_path, wake)


def apply_auto_schedule(cfg, events_path):
    """把推導出來的作息寫進 cfg。回傳有沒有變動。

    起床時間一律重推：它不在面板上，使用者沒有別的方式表態，推導是唯一的來源。
    就寢時間相反，使用者說過就聽他的（bedtime_manual），推導只給初始值。
    深夜起點則永遠重算——它是就寢時間的導出值，來源變了它就該跟著變。
    """
    if not cfg.get("auto_schedule", True):
        return False
    before = (cfg.get("day_rollover_hour"), cfg.get("late_night_start_hour"))

    wake = infer_wake_hour(events_path)
    if wake is not None:
        cfg["day_rollover_hour"] = wake
    wake = cfg.get("day_rollover_hour", DEFAULTS["day_rollover_hour"])

    # 就寢時間跟起床時間一樣：使用者說過就聽他的，推導只負責給初始值。
    # 深夜起點則永遠重算——它是就寢時間的導出值，來源變了它就該跟著變。
    if not cfg.get("bedtime_manual"):
        cfg["bedtime_hour"] = infer_bedtime(events_path, wake)
    cfg["late_night_start_hour"] = late_start_from_bedtime(
        cfg.get("bedtime_hour", DEFAULTS["bedtime_hour"]))

    return (cfg.get("day_rollover_hour"), cfg.get("late_night_start_hour")) != before


# ---------------------------------------------------------------- 開機自啟

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "Sipbar"
OLD_RUN_VALUE = "WaterPet"      # 改名前的登錄值，由 _migrate_autostart 搬掉

# 更早期還有一版是手動放在 Startup 資料夾的捷徑（`喝水動態島.lnk`）。
# 那個檔已於 2026-08-15 從這台機器移除並封存到 ..\archive\，而這個工具目前
# 只有一個使用者、一台機器，所以對應的偵測與清除程式碼在改名時一併刪掉了。
# 不是留著比較安全：留著就得同時維護「舊捷徑」與「舊登錄值」兩條相容路徑，
# 而其中一條指向的檔案已經不存在——死掉的相容碼會讓人以為它還在防什麼。
#
# 登錄檔的 Run 鍵比 Startup 捷徑好，這個判斷沒變：工作管理員的「啟動應用程式」
# 分頁看得到、也關得掉；Startup 資料夾裡的捷徑反而是使用者找不到的那一種。


def _migrate_autostart():
    """把改名前的登錄值換成新的。回傳有沒有搬。

    不能只是新增一筆。舊值留著的話，開機時兩筆都會執行——單一實例的
    mutex 會擋掉第二個，看起來沒事，但使用者在工作管理員裡會看到兩筆自啟項，
    而設定頁的開關只認得其中一筆：關掉之後另一筆照樣把程式拉起來。
    所以是「寫新的、刪舊的」，一次做完。
    """
    try:
        import winreg
    except ImportError:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_READ) as k:
            try:
                winreg.QueryValueEx(k, OLD_RUN_VALUE)
            except OSError:
                return False            # 沒有舊的，不用做事
    except OSError:
        return False
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            # 指令重新產生而不是照抄舊的：舊值可能還指向搬過家之前的路徑。
            winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, autostart_command())
            winreg.DeleteValue(k, OLD_RUN_VALUE)
        return True
    except OSError:
        return False


def refresh_autostart_path():
    """自啟開著、但登錄檔指向別的地方，就改指到現在這個執行檔。回傳有沒有改。

    這是給「更新」用的。攜帶版沒有安裝程式，使用者拿到新版就是解壓縮——
    而他很可能解到新的資料夾（`Sipbar-0.10.0-beta\\` 之類），舊的那包還在原地。

    不修的話會靜默出錯，而且很難發現：
      - `autostart_enabled()` 只看「登錄檔有沒有這一筆」，不看它指去哪
      - 所以設定頁照樣顯示「開機時啟動」是開的
      - 但每天開機拉起來的是**舊版**
      - 使用者以為自己更新了，其實用的還是舊的，連版本號都對不上

    只在已經開著自啟時才動。沒開就不要自作主張幫他開。
    """
    if not autostart_enabled():
        return False
    want = autostart_command()
    if _run_key_value() == want:
        return False
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, want)
        return True
    except (ImportError, OSError):
        return False


def autostart_command():
    """開機要執行的指令。打包成 exe 之後直接指向自己。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # 用 pythonw.exe 才不會跳出主控台視窗
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else sys.executable
    return f'"{exe}" "{os.path.join(APP_DIR, "island.py")}"'


def _run_key_value():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            return winreg.QueryValueEx(k, RUN_VALUE)[0]
    except (ImportError, OSError):
        return None


def autostart_enabled():
    return _run_key_value() is not None


def set_autostart(on):
    """開／關開機自啟。回傳有沒有成功。

    關掉時舊名字那筆也一起刪。改名後可能兩筆並存（使用者在遷移跑之前
    就先關過自啟，新的沒建、舊的還在），只刪新的等於留一個會說謊的開關：
    面板顯示「關」，開機照樣被拉起來。
    """
    try:
        import winreg
    except ImportError:
        return False
    try:
        if on:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                                    winreg.KEY_SET_VALUE) as k:
                    for name in (RUN_VALUE, OLD_RUN_VALUE):
                        try:
                            winreg.DeleteValue(k, name)
                        except OSError:
                            pass          # 本來就沒有
            except OSError:
                pass                      # 連 Run 鍵都沒有
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- 資料

def reset_data():
    """刪掉紀錄與狀態，保留設定。回傳刪掉幾個檔。

    設定要留著：使用者按「清除所有資料」是想把數字歸零重來，
    不是想把體重跟間隔一起忘掉再填一次。
    """
    n = 0
    for p in (STATE_PATH, EVENTS_PATH):
        guard_real_write(p)          # 刪除比覆蓋更不可逆，這裡更該擋
        if os.path.exists(p):
            try:
                os.remove(p)
                n += 1
            except OSError:
                pass
    return n

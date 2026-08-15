# -*- coding: utf-8 -*-
"""設定：檔案位置、讀寫、推導、開機自啟、資料清除。

**設定面板只有四項，這是刻意的。**

篩選標準只有一條：不改就會讓工具對這個人失效。體重（目標差一倍）、
提醒間隔（每個人在電腦前的時間結構不同）、螢幕（多螢幕猜不到）、
開機自啟（沒人會自己去 Startup 資料夾）。其餘全部寫死或自動推導。

刻意不做的東西更重要：**沒有「關閉提醒」總開關、沒有「稍後提醒」、
沒有「關掉倒地狀態」、沒有提醒強度調整。** 這個工具的核心是
「你無法 dismiss 一個狀態」，而設定面板在結構上就是一顆巨大的關閉鍵——
開放什麼就等於允許使用者把它關到失效，然後變成「靜音但沒解除安裝」，
在系統裡躺半年。暫停 2 小時已經是出口，那是唯一一個。

實測支持這個決定：22 次提醒中有 5 次升級到虛弱、2 次到倒地，
七次全部以喝水收場（最快 1 秒、最慢 33 分）。升級機制有效到使用者
根本沒感覺它存在——那不是該給人關掉的東西。
"""

import json
import os
import shutil
import sys
from datetime import datetime

from motion import clamp

# 還在 beta：功能齊了，但只在一台機器上跑過、只有一個使用者的資料。
# 1.0 要等別人裝過、而且撐過 14 天檢核再說。
#
# 改這個字串會讓程式在下次啟動時打一次招呼（滑下來 4 秒），那是刻意的——
# 版本換了就值得說一聲。見 island.main() 的 greeted_version。
VERSION = "0.9.0-beta"

APP_NAME = "WaterPet"

# 設定檔跟著資料走，不放在程式旁邊。
# 打包成 exe 裝進 Program Files 之後那個目錄不可寫，寫入會**靜默**失敗——
# 使用者改了設定、按了儲存、什麼錯誤都沒有，重開之後全部復原。
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
EVENTS_PATH = os.path.join(DATA_DIR, "events.jsonl")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LEGACY_CONFIG_PATH = os.path.join(APP_DIR, "config.json")

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

    # --- 自動推導，使用者不用回答 ---
    # 「你幾點睡」這個問題程式自己看得到（見 infer_schedule），而且真正相關的
    # 不是睡覺時間，是「電腦日什麼時候結束」。頭幾天資料不夠就用這裡的預設。
    "auto_schedule": True,
    "day_rollover_hour": 4,
    "late_night_start_hour": 23,

    # --- 寫死，不上面板 ---
    # 單位是「補水次數」不是「杯」：被提醒時你只會喝幾口，用「杯」當單位會逼你
    # 虛報、或因為「才喝兩口」而不敢按——兩種都會讓數字失真。
    "ml_per_drink_estimate": 200,   # 僅供統計顯示，會標明是估算
    # 抖動改成比例：固定 ±10 分在間隔 70 分時合理，設成 30 分就太大了。
    "interval_jitter_pct": 15,
    # 深夜間隔是主間隔的倍數，不是獨立參數——兩個各自可調只會調到互相矛盾。
    "late_night_ratio": 1.45,
    "idle_threshold_min": 15,
    "escalate_weak_min": 15,
    "escalate_collapsed_min": 40,
    "tick_seconds": 5,
    "thirsty_hold_seconds": 6,
    "weak_hold_seconds": 8,
    "satisfied_flash_seconds": 1.8,
    "face_style": "pixel",

    # --- 內部狀態 ---
    # 啟動時滑下來 4 秒是為了解決「我不知道它在不在」，對已經知道的人是每天一次的
    # 噪音。用預設行為解掉，不做成開關——每個設定項都是推給使用者的一個決定。
    "greeted_version": None,
}

TARGET_MIN, TARGET_MAX = 4, 12
INTERVAL_CHOICES = (30, 45, 60, 75, 90)


# ---------------------------------------------------------------- 讀寫

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


def _upgrade_keys(raw):
    """舊版的鍵名換成新的。使用者調過的值不能因為改版就被丟掉。"""
    # interval_jitter_min（固定分鐘）-> interval_jitter_pct（比例）
    if "interval_jitter_min" in raw and "interval_jitter_pct" not in raw:
        base = raw.get("interval_min") or DEFAULTS["interval_min"]
        raw["interval_jitter_pct"] = int(round(raw["interval_jitter_min"] / base * 100))
    # late_night_interval_min（絕對值）-> late_night_ratio（倍數）
    if "late_night_interval_min" in raw and "late_night_ratio" not in raw:
        base = raw.get("interval_min") or DEFAULTS["interval_min"]
        raw["late_night_ratio"] = round(raw["late_night_interval_min"] / base, 2)
    # 使用者自己調過目標，升級後不能被體重推導蓋掉
    if "daily_target_drinks" in raw and "target_manual" not in raw:
        raw["target_manual"] = raw["daily_target_drinks"] != DEFAULTS["daily_target_drinks"]
    # 換算完就把舊鍵刪掉。留著沒有壞處（沒有人讀），但使用者打開設定檔會看到
    # 兩組互相矛盾的值，不知道哪個才算數——發布出去的東西不該讓人猜。
    for dead in ("interval_jitter_min", "late_night_interval_min"):
        raw.pop(dead, None)
    return raw


def load_config():
    cfg = dict(DEFAULTS)
    _migrate_legacy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(_upgrade_keys(json.load(f)))
        except (OSError, ValueError):
            pass          # 壞掉的設定檔用預設值頂著，不要讓程式起不來
    else:
        save_config(cfg)
    return cfg


def save_config(cfg):
    """寫設定。先寫暫存再換檔，中途斷電不會留下半個檔。"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- 推導

def target_from_weight(kg):
    """體重換算每日補水次數。回傳 None 代表沒填體重。

    體重 × 30cc  = 每日總需求。國健署「成人 6–8 杯 × 240ml = 1440–1920cc」，
                   65kg 推出 1950cc，兩者相符。
    × 0.7        = 工具承擔的比例。起床那杯（建議 300–500cc）與三餐湯水
                   發生在它管不到的地方，只算坐在電腦前的部分。
    ÷ 200cc      = 一次的量。國健署明講 1 小時內不超過 1000cc，小口慢喝。

    65kg → 6.8 → 7 次，正是規劃文件手算出來的數字。
    """
    if not kg:
        return None
    return int(clamp(round(kg * 30 * 0.7 / 200), TARGET_MIN, TARGET_MAX))


def effective_target(cfg):
    """實際要用的每日次數：手動覆寫 > 體重推導 > 預設。"""
    if cfg.get("target_manual"):
        return int(clamp(cfg.get("daily_target_drinks") or DEFAULTS["daily_target_drinks"],
                         TARGET_MIN, TARGET_MAX))
    return target_from_weight(cfg.get("weight_kg")) or DEFAULTS["daily_target_drinks"]


def late_night_interval(cfg):
    """深夜間隔＝主間隔 × 倍數。不是獨立參數，避免兩個各自可調而互相矛盾。"""
    return int(round(cfg["interval_min"] * cfg.get("late_night_ratio",
                                                   DEFAULTS["late_night_ratio"])))


# ---------------------------------------------------------------- 作息推導

LOOKBACK_DAYS = 14
MIN_EVENTS = 20        # 少於這個量的樣本，任何推導都只是在放大雜訊
MIN_QUIET_H = 4        # 安靜時段至少要這麼長才算數
QUIET_RATIO = 0.15     # 低於「平均每小時」這個比例就算安靜
LATE_BEFORE_H = 6      # 深夜模式從換日往前幾小時開始

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


def infer_schedule(events_path):
    """推導 (換日時間, 深夜模式起點)，資料不夠就回 None。

    **不問使用者「你幾點睡」。** 那個答案程式自己看得到，而且真正相關的
    也不是睡覺時間，是「你從來不在電腦前的是哪一段」——這個工具只在
    電腦前運作，牆上時鐘幾點跟它無關。

    做法：把所有活動事件攤成 24 格直方圖，找出最長的一段安靜時間，
    **換日就設在那一段的起點**。理由很直接：那是一天當中最安全的換日點，
    因為按定義你不在。換日設在有活動的時段，凌晨的工作就會被切成兩天、
    次數莫名歸零。

    深夜模式從換日往前推 6 小時。它的目的是「睡前別灌水」，而睡前
    就是換日之前那幾個小時——只推導一個量，另一個跟著走，
    兩個各自推導只會推出互相矛盾的組合。

    以使用者 2026-08-10～08-14 的真實資料驗證：54 筆活動事件中
    05:00–10:00 完全是零，最長安靜段起點 05:00 → 換日 05:00、深夜 23:00，
    與他手動調出來的值一致。

    比「取每天結束時刻的平均」穩健得多：那個做法只有 4 個樣本、
    而且會被一次 4 小時的下午外出誤判成一天的結束。這個做法用上全部
    54 筆事件，而且是眾數性質的統計，不會被個別的晚睡拉走。
    """
    hist = activity_hours(events_path)
    if sum(hist) < MIN_EVENTS:
        return None
    run = _longest_quiet_run(hist)
    if not run or run[1] < MIN_QUIET_H:
        return None
    rollover = run[0] % 24
    return rollover, (rollover - LATE_BEFORE_H) % 24


def apply_auto_schedule(cfg, events_path):
    """把推導出來的作息寫進 cfg。回傳有沒有變動。"""
    if not cfg.get("auto_schedule", True):
        return False
    got = infer_schedule(events_path)
    if not got:
        return False
    rollover, late = got
    if (cfg.get("day_rollover_hour"), cfg.get("late_night_start_hour")) == (rollover, late):
        return False
    cfg["day_rollover_hour"], cfg["late_night_start_hour"] = rollover, late
    return True


# ---------------------------------------------------------------- 開機自啟

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "WaterPet"

# 舊版是手動放在 Startup 資料夾的捷徑。登錄檔的 Run 鍵比較好，因為
# 工作管理員的「啟動應用程式」分頁看得到、也關得掉——Startup 資料夾裡的
# 捷徑反而是使用者找不到的那一種。
LEGACY_STARTUP_LNK = os.path.join(
    os.environ.get("APPDATA", ""),
    r"Microsoft\Windows\Start Menu\Programs\Startup\喝水動態島.lnk")


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
    """兩種機制任一存在都算開著——否則開關會對舊版的捷徑說謊。"""
    return _run_key_value() is not None or os.path.exists(LEGACY_STARTUP_LNK)


def set_autostart(on):
    """開／關開機自啟。回傳有沒有成功。

    關閉時連舊版的 Startup 捷徑一起移除：留著它會讓程式照樣自動啟動，
    而開關顯示「關」——一個會說謊的開關比沒有開關更糟。
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
                    winreg.DeleteValue(k, RUN_VALUE)
            except OSError:
                pass                      # 本來就沒有
            if os.path.exists(LEGACY_STARTUP_LNK):
                try:
                    os.remove(LEGACY_STARTUP_LNK)
                except OSError:
                    return False
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
        if os.path.exists(p):
            try:
                os.remove(p)
                n += 1
            except OSError:
                pass
    return n

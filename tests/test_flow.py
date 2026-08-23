# -*- coding: utf-8 -*-
"""端對端：把一個真的島從「第一次啟動」推到「換日」，驗每一個接縫。

## 為什麼要有這一支

其他測試各自驗一個零件：test_island 驗狀態機、test_streak 驗連續天數、
test_settings 驗設定的讀寫與推導、test_sound 驗音效。每一支都很細，
但**沒有一支走過完整的一趟**。

而這個專案這一輪出的問題幾乎全在接縫上，不在零件裡：

- 引導按下「開始」之後，音效的選擇有沒有真的被存下來
- 引導有沒有擅自把作息標成手動
- 補水之後，開著的紀錄視窗有沒有跟著更新
- 退回一次記錄，倒數有沒有一起還原

這些每一個都是「兩個零件之間」的事，各自的單元測試都是綠的。

## 走的路線

    第一次啟動（沒有設定檔）
      -> 引導：作息、音效、開機自啟
      -> 設定被寫回去，標記引導看過了
      -> 到間隔：口渴 -> 忽略 15 分：虛弱（出聲）-> 忽略 40 分：倒地（出聲）
      -> 補水：次數 +1、倒數歸零、紀錄視窗跟著更新
      -> 退回：次數 −1、狀態與倒數回到按之前
      -> 補到達標：當天不再出現
      -> 換日：歸零
      -> 重看導覽：不會改掉現有設定

用法：python tests/test_flow.py
"""
import io
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import settings as aps  # noqa: E402

# ---------------------------------------------------------------- 沙箱
# 一定要在 import island 之前。島在模組層級就把三個路徑複製走了，
# 晚一步指就來不及，而寫進去的是使用者真實的紀錄。
BOX = tempfile.mkdtemp(prefix="sipbar_flow_")
aps.DATA_DIR = os.path.join(BOX, "data")
aps.CONFIG_PATH = os.path.join(aps.DATA_DIR, "config.json")
aps.STATE_PATH = os.path.join(aps.DATA_DIR, "state.json")
aps.EVENTS_PATH = os.path.join(aps.DATA_DIR, "events.jsonl")
os.makedirs(aps.DATA_DIR, exist_ok=True)

# 開機自啟會寫真的登錄檔。這一支不驗登錄檔，只驗「引導有沒有把值傳下去」，
# 所以換成假的，順便把它收到的參數記下來。
AUTOSTART = []
aps.set_autostart = lambda on: (AUTOSTART.append(on), True)[1]
aps.autostart_enabled = lambda: bool(AUTOSTART and AUTOSTART[-1])

import island as isl  # noqa: E402

isl.DATA_DIR = aps.DATA_DIR
isl.STATE_PATH = aps.STATE_PATH
isl.EVENTS_PATH = aps.EVENTS_PATH

IDLE = [0.0]
isl.idle_seconds = lambda: IDLE[0]

# 音效不要真的響，但要看得到它什麼時候被叫。
PLAYED = []
isl.sound.play = lambda name: PLAYED.append(name) or True

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

import dashboard  # noqa: E402
import onboard  # noqa: E402
import stats_window as sw  # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + f"{label}: {got!r}" +
          ("" if ok else f"  (預期 {want!r})"))
    if not ok:
        fails.append(label)


def ticks(w, n):
    for _ in range(n):
        w.tick()


def to_reminder(w):
    """跑到剛好發出提醒。間隔有 ±15% 抖動，所以用算的不要寫死。"""
    ticks(w, int(w.interval_s / 60) + 1)


# ================================================================ 1
print("1. 第一次啟動：沒有設定檔，該跑引導")
cfg = aps.load_config()
check("設定檔被建出來", os.path.exists(aps.CONFIG_PATH), True)
check("還沒看過引導", cfg["onboarded"], False)
check("音效預設開著", cfg["sound_enabled"], True)
check("作息預設是自動", (cfg["wake_manual"], cfg["bedtime_manual"]), (False, False))

cfg["tick_seconds"] = 60          # 一 tick 當一分鐘，快轉用
w = isl.Island(cfg)
for t in (w.tick_timer, w.frame, w.hold_timer, w.peek_timer):
    t.stop()

# ================================================================ 2
print("\n2. 引導按下「開始」：選擇要被存下來")
# 模擬使用者：調了起床（10 點）、沒碰就寢、關掉音效、留著開機自啟
win = onboard.OnboardWindow(
    wake=cfg["day_rollover_hour"], bedtime=cfg["bedtime_hour"],
    sound_on=cfg["sound_enabled"], autostart=True,
    wake_manual=cfg["wake_manual"], bedtime_manual=cfg["bedtime_manual"])
win.frame.stop()
win.wake_pick.set_hour(10)
win.sound_on.set_on(False)
win.finished.connect(lambda r: w._onboarding_done(r, first_run=True))
win._emit_finish()

check("起床存進去了", w.cfg["day_rollover_hour"], 10)
check("動過的那一項標記為手動", w.cfg["wake_manual"], True)
check("沒動過的那一項維持自動", w.cfg["bedtime_manual"], False)
check("音效的選擇存下來了", w.cfg["sound_enabled"], False)
check("開機自啟傳下去了", AUTOSTART, [True])
check("標記為看過引導", w.cfg["onboarded"], True)
# 深夜起點是就寢的導出值，作息改完要當場重算，不能停在引導之前的數字
check("深夜起點跟著重算",
      w.cfg["late_night_start_hour"],
      aps.late_start_from_bedtime(w.cfg["bedtime_hour"]))
saved = aps.load_config()
check("而且真的寫進設定檔", saved["day_rollover_hour"], 10)

# ================================================================ 3
print("\n3. 一天的循環：提醒 -> 升級 -> 出聲")
w.cfg["sound_enabled"] = True     # 這一段要驗出聲，把它開回來
PLAYED.clear()
to_reminder(w)
check("到間隔就口渴", w.state, isl.THIRSTY)
check("一般提醒不出聲", PLAYED, [])

ticks(w, w.cfg["escalate_weak_min"] + 1)
check("忽略 15 分變虛弱", w.state, isl.WEAK)
check("虛弱響一聲", PLAYED, ["weak"])

ticks(w, w.cfg["escalate_collapsed_min"] - w.cfg["escalate_weak_min"] + 1)
check("忽略 40 分倒地", w.state, isl.COLLAPSED)
check("倒地是另一個聲音", PLAYED, ["weak", "collapsed"])

print("\n3b. 離開電腦不計時，也不會對著空房間出聲")
PLAYED.clear()
w.drinks = 0
w._enter(isl.THIRSTY)
w.active_s = 0.0
IDLE[0] = (w.cfg["idle_threshold_min"] + 5) * 60
ticks(w, 60)
check("閒置時 active_s 不動", w.active_s, 0.0)
check("也沒有出聲", PLAYED, [])
IDLE[0] = 0.0

# ================================================================ 4
print("\n4. 補水：次數、倒數、紀錄視窗")
w._enter(isl.NORMAL)
w.drinks = 0
w.active_s = w.interval_s + 600
stats = sw.open_window(dict(w.cfg), isl.EVENTS_PATH)
stats.frame.stop()
w._stats_win = stats
before_shown = stats.data["today"]["drinks"]

w._last_drink_at = -1e9
w.drink()
check("次數 +1", w.drinks, 1)
check("倒數歸零", w.active_s, 0.0)
check("進入達標確認", w.state, isl.SATISFIED)
check("開著的紀錄視窗跟著更新",
      stats.data["today"]["drinks"], before_shown + 1)

# ================================================================ 5
print("\n5. 退回一次記錄：連倒數一起還原")
w._enter(isl.NORMAL)
w.active_s = w.interval_s + 900
ticks(w, 1)                                   # 讓它進入提醒狀態
state_before = w.state
active_before, interval_before = w.active_s, w.interval_s
w._last_drink_at = -1e9
w.drink()
check("記了一次", w.drinks, 2)

w.undo_drink()
check("次數退回去", w.drinks, 1)
check("累積的時間也還原", w.active_s, active_before)
check("那一輪的間隔也還原", w.interval_s, interval_before)
check("島回到按下去之前那一級", w.state, state_before)
# 紀錄檔是只增不改的：drink 還在，undo 是補上去的
rows = [r for r in open(isl.EVENTS_PATH, encoding="utf-8") if r.strip()]
check("原始的 drink 沒有被刪掉", any('"drink"' in r for r in rows), True)
check("補了一筆 undo", any('"undo"' in r for r in rows), True)
days = dashboard.load_days(isl.EVENTS_PATH, 5)
check("統計也扣掉了", days[w.day]["drinks"], w.drinks)

# ================================================================ 6
print("\n6. 補到達標：當天不再出現")
target = w.cfg["daily_target_drinks"]
while w.drinks < target:
    w._last_drink_at = -1e9
    w.drink()
check("達到目標", w.drinks, target)
check("訊息是達標", w.message, "今天達標了")
# 這一支從第一次啟動走到這裡，所以這是這個使用者的第一次達標——
# 紀錄視窗做得比島完整，而唯一的入口是右鍵，不講就沒有人會發現。
# 接縫在這裡：drink() 要讀設定、寫設定、再把那句話交給島顯示。
check("第一次達標告訴他紀錄在哪", w.sub_message, "右鍵可以看紀錄")
check("而且真的寫回設定檔",
      json.load(io.open(aps.CONFIG_PATH, encoding="utf-8"))["records_hinted"], True)
w._settle()
ticks(w, 600)
check("跑 600 分鐘仍然不出現", w.sp_reveal.target, 0.0)

# ================================================================ 7
print("\n7. 換日：歸零重新開始")
w.day = "1999-01-01"
w.tick()
check("次數歸零", w.drinks, 0)
check("狀態回到正常", w.state, isl.NORMAL)

# ================================================================ 8
print("\n8. 改設定：不能偷偷重置當前這一輪倒數")
w._enter(isl.NORMAL)
w.active_s = 1234.0
newcfg = dict(w.cfg)
newcfg["interval_min"] = 45
w.apply_config(newcfg)
check("倒數沒有被重置", w.active_s, 1234.0)
check("新的間隔有生效", w.cfg["interval_min"], 45)

# ================================================================ 9
print("\n9. 重看導覽：不會改掉現有的設定")
w.cfg["sound_enabled"] = False
w.cfg["wake_manual"] = True
w.cfg["day_rollover_hour"] = 10
AUTOSTART.clear()
AUTOSTART.append(False)                       # 假裝使用者把自啟關了
w2 = onboard.OnboardWindow(
    wake=w.cfg["day_rollover_hour"], bedtime=w.cfg["bedtime_hour"],
    sound_on=w.cfg["sound_enabled"],
    autostart=aps.autostart_enabled(),
    wake_manual=w.cfg["wake_manual"], bedtime_manual=w.cfg["bedtime_manual"])
w2.frame.stop()
got = {}
w2.finished.connect(got.update)
w2._emit_finish()                             # 一路按下一步，什麼都沒碰
check("音效維持關著", got["sound_enabled"], False)
check("自啟維持關著", got["autostart"], False)
check("起床維持手動", got["wake_manual"], True)
check("起床的值沒被動過", got["day_rollover_hour"], 10)
check("就寢維持自動", got["bedtime_manual"], False)
w2.close()

# ================================================================ 99
print("\n99. 整支測試不能碰到使用者真實的資料檔")
check("防線沒有攔截到任何寫入", aps.real_write_violations(), [])

stats.close()
shutil.rmtree(BOX, ignore_errors=True)
print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 項失敗：{fails}"))
sys.exit(1 if fails else 0)

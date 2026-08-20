# -*- coding: utf-8 -*-
"""驗證 settings.py：體重推導、作息推導、鍵名升級、舊檔遷移、熱套用不重置倒數。"""
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

# 台灣 Windows 的主控台預設是 cp950，而被驗的 UI 文案裡有 Big5 沒有的字（麵包屑的 ‹）。
# 不放寬錯誤處理的話，測試會在「印出結果」那一步崩掉——看起來像測試沒過，其實是主控台
# 印不出來。驗文案的測試不能因為文案本身而掛掉。
sys.stdout.reconfigure(errors="replace")

import settings as ap  # noqa: E402

# ---------------------------------------------------------------- 沙箱
# 這段一定要在任何測試之前。
# 這支測試會呼叫 SettingsPage._emit()，而 _emit() 會 save_config()——
# 沒有沙箱的話，它寫的是使用者真實的 %LOCALAPPDATA%\WaterPet\config.json，
# 跑一次測試就把人家調好的設定洗成測試用的預設值。
# 這件事真的發生過（目標 10 次 / 間隔 45 分被洗成 7 次 / 60 分），
# 而且沒有任何錯誤訊息——測試全綠，設定沒了。
SANDBOX = tempfile.mkdtemp(prefix="wp_settings_")
ap.DATA_DIR = os.path.join(SANDBOX, "data")
ap.CONFIG_PATH = os.path.join(ap.DATA_DIR, "config.json")
ap.STATE_PATH = os.path.join(ap.DATA_DIR, "state.json")
ap.EVENTS_PATH = os.path.join(ap.DATA_DIR, "events.jsonl")
ap.LEGACY_CONFIG_PATH = os.path.join(SANDBOX, "legacy_config.json")
os.makedirs(ap.DATA_DIR, exist_ok=True)

fails = []


def check(label, got, want):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + f"{label}: {got}" +
          ("" if ok else f"  (預期 {want})"))
    if not ok:
        fails.append(label)


TMP = os.path.join(SANDBOX, "work")
os.makedirs(TMP, exist_ok=True)


def write_events(rows):
    """rows = [(相對現在幾小時前, 事件)]，回傳事件檔路徑。"""
    path = os.path.join(TMP, f"ev_{len(os.listdir(TMP))}.jsonl")
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    with open(path, "w", encoding="utf-8") as f:
        for when, ev in rows:
            f.write(json.dumps({"ts": when.isoformat(timespec="seconds"),
                                "event": ev, "day": when.date().isoformat()},
                               ensure_ascii=False) + "\n")
    return path


print("1. 體重換算每日次數")
check("65kg（規劃文件手算出來的 7）", ap.target_from_weight(65), 7)
check("50kg", ap.target_from_weight(50), 5)
check("90kg", ap.target_from_weight(90), 9)
check("沒填", ap.target_from_weight(None), None)
# 夾住上下限：極端體重不該推出一天 2 次或 20 次這種沒有意義的目標
check("30kg 夾在下限", ap.target_from_weight(30), ap.TARGET_MIN)
check("200kg 夾在上限", ap.target_from_weight(200), ap.TARGET_MAX)

print("\n2. 有效目標：手動覆寫 > 體重推導 > 預設")
check("只有體重", ap.effective_target({"weight_kg": 90}), 9)
check("手動覆寫贏過體重",
      ap.effective_target({"weight_kg": 90, "target_manual": True,
                           "daily_target_drinks": 5}), 5)
check("兩者皆無用預設", ap.effective_target({}), ap.DEFAULTS["daily_target_drinks"])

print("\n3. 深夜間隔是主間隔的倍數，不是獨立參數")
check("75 分 × 1.45", ap.late_night_interval({"interval_min": 75, "late_night_ratio": 1.45}), 109)
check("深夜一定比白天長",
      ap.late_night_interval({"interval_min": 30, "late_night_ratio": 1.45}) > 30, True)

print("\n4. 作息推導：起床＝安靜段的結束，不是開始")
# 造一份「每天 09:00-23:00 在電腦前」的紀錄：安靜段是 00:00-09:00
base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
rows = []
for d in range(6):
    for h in range(9, 24):
        rows.append((base + timedelta(days=d, hours=h), "drink"))
p = write_events(rows)
# 取結束（回到電腦前）而不是開始（停止用電腦）。兩者都落在空檔裡都能當換日用，
# 但拿「停止用電腦」當換日，哪天做過頭就會在還在工作時把當天次數歸零。
check("起床＝安靜段結束", ap.infer_wake_hour(p), 9)
# 每天最後活動 23:00，起床 09:00 → 起床後 14 小時；往前 3 小時 = 20:00
check("深夜模式＝每日最後活動中位數往前 3 小時", ap.infer_late_hour(p, 9), 20)
check("infer_schedule 兩個一起給", ap.infer_schedule(p), (9, 20))

print("\n5. 資料不足時不亂猜")
check("空檔案", ap.infer_schedule(write_events([])), None)
few = [(base + timedelta(hours=i), "drink") for i in range(5)]
check("只有 5 筆", ap.infer_schedule(write_events(few)), None)
# 整天都有活動 = 沒有安靜段，推不出東西也不能硬給一個
allday = []
for d in range(4):
    for h in range(24):
        allday.append((base + timedelta(days=d, hours=h), "drink"))
check("整天都在用", ap.infer_schedule(write_events(allday)), None)

print("\n6. 程式自己的記帳事件不算活動")
# day_start 每天固定在同一個時刻，若被當成活動就會把安靜段填掉，推導自我實現
noise = list(rows)
for d in range(6):
    noise.append((base + timedelta(days=d, hours=4), "day_start"))
check("day_start 不影響推導", ap.infer_wake_hour(write_events(noise)), 9)

print("\n6b. 起床時間手動指定後，深夜模式跟著它重算")
manual = dict(ap.DEFAULTS)
manual["wake_manual"] = True
manual["day_rollover_hour"] = 11
_ev = ap.EVENTS_PATH
try:
    ap.EVENTS_PATH = p
    ap.apply_auto_schedule(manual, p)
finally:
    ap.EVENTS_PATH = _ev
check("手動的起床時間不被推導蓋掉", manual["day_rollover_hour"], 11)
# 這份假資料是 09:00–23:00 活動，使用者卻說 11:00 才起床——起床時間落在
# 自己的活動時段裡。以 11:00 切天，「當天最後一次活動」會變成隔天早上 10:00
# （起床後 23 小時），往回推 3 小時得出 07:00，是垃圾。
# 落在合理範圍外就退回「起床 − 11 小時」。
check("起床時間與活動矛盾時退回推估值", manual["late_night_start_hour"], 0)

print("\n6c. 深夜起點是就寢時間的導出值，不是獨立參數")
# 使用者設的是「就寢時間」（他知道的事實），不是「深夜幾點開始」（系統概念）。
check("就寢 02:00 -> 深夜起點 23:00", ap.late_start_from_bedtime(2), 23)
check("就寢 24:00 -> 深夜起點 21:00", ap.late_start_from_bedtime(0), 21)
# infer_bedtime 必須是 infer_late_hour 的反函式。兩份各自推導一定會漂開，
# 而畫面上寫的就寢時間跟程式實際用的深夜起點一旦對不起來，介面就在說謊。
check("推導的就寢與深夜起點互為反函式",
      ap.late_start_from_bedtime(ap.infer_bedtime(p, 9)), ap.infer_late_hour(p, 9))
# 手動設過就不再被推導覆蓋——跟 wake_manual 同一套規則
man = dict(ap.DEFAULTS)
man["bedtime_manual"] = True
man["bedtime_hour"] = 3
ap.apply_auto_schedule(man, p)
check("手動的就寢時間不被推導蓋掉", man["bedtime_hour"], 3)
check("深夜起點仍從手動值重算", man["late_night_start_hour"], 0)
# 沒標記手動就該被推導接管
auto = dict(ap.DEFAULTS)
auto["bedtime_hour"] = 3
ap.apply_auto_schedule(auto, p)
check("沒設過就交給推導", auto["bedtime_hour"], ap.infer_bedtime(p, auto["day_rollover_hour"]))

print("\n7. 舊鍵名升級，使用者調過的值不能弄丟")
raw = {"interval_min": 60, "interval_jitter_min": 12,
       "late_night_interval_min": 90, "daily_target_drinks": 10}
up = ap._upgrade_keys(dict(raw))
check("固定分鐘的抖動 -> 比例", up["interval_jitter_pct"], 20)
check("深夜絕對值 -> 倍數", up["late_night_ratio"], 1.5)
check("調過目標就標記為手動", up["target_manual"], True)
# 換算完舊鍵要清掉，否則設定檔裡會並存兩組互相矛盾的值
check("舊鍵已移除", [k for k in ("interval_jitter_min", "late_night_interval_min")
                     if k in up], [])
untouched = ap._upgrade_keys({"daily_target_drinks": ap.DEFAULTS["daily_target_drinks"]})
check("沒調過目標就不標記", untouched["target_manual"], False)

print("\n7b. 引導只給第一次啟動的人看")
# 舊版寫的設定檔沒有這個鍵。對已經用了兩週的人跳出「桌上現在有水嗎」是搞錯對象。
check("升級的舊設定檔視為看過了", ap._upgrade_keys({"interval_min": 60})["onboarded"], True)
# 但不能因此讓中途關掉引導的新使用者也再也看不到：
# 全新安裝寫進檔案的是明確的 False，setdefault 不會去動已經存在的鍵。
check("新安裝寫的 False 不會被蓋成 True",
      ap._upgrade_keys({"onboarded": False})["onboarded"], False)
check("跑完引導的 True 保持不變",
      ap._upgrade_keys({"onboarded": True})["onboarded"], True)

print("\n8. 設定檔從程式旁邊搬到資料夾")
_dir, _cfg, _legacy = ap.DATA_DIR, ap.CONFIG_PATH, ap.LEGACY_CONFIG_PATH
try:
    ap.DATA_DIR = os.path.join(TMP, "migrate")
    ap.CONFIG_PATH = os.path.join(ap.DATA_DIR, "config.json")
    ap.LEGACY_CONFIG_PATH = os.path.join(TMP, "old_config.json")
    with open(ap.LEGACY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"interval_min": 45, "weight_kg": 72}, f)
    check("有搬", ap._migrate_legacy(), True)
    check("新位置讀得到舊值", ap.load_config()["interval_min"], 45)
    check("舊檔留著當備份", os.path.exists(ap.LEGACY_CONFIG_PATH), True)
    # 新位置已經有檔案時不能再蓋回去，否則使用者的新設定會被舊檔洗掉
    check("不重複搬", ap._migrate_legacy(), False)
finally:
    ap.DATA_DIR, ap.CONFIG_PATH, ap.LEGACY_CONFIG_PATH = _dir, _cfg, _legacy

print("\n8c. 改名：舊資料夾整份接過來，只做一次")
# 改名前叫 WaterPet。不搬的話使用者的設定與紀錄會變孤兒——程式建一個空的
# 新資料夾，而他的紀錄還躺在舊的裡面，沒有任何錯誤訊息。
_mig = tempfile.mkdtemp(prefix="wp_rename_")
_old_dir = os.path.join(_mig, ap.OLD_APP_NAME)
_new_dir = os.path.join(_mig, ap.APP_NAME)
os.makedirs(_old_dir)
json.dump({"weight_kg": 65, "interval_min": 60},
          open(os.path.join(_old_dir, "config.json"), "w"))
json.dump({"drinks": 9}, open(os.path.join(_old_dir, "state.json"), "w"))
open(os.path.join(_old_dir, "events.jsonl"), "w").write('{"event":"drink"}\n')
_keep = (ap.DATA_DIR, ap.CONFIG_PATH, ap.STATE_PATH, ap.EVENTS_PATH)
try:
    ap.DATA_DIR = _new_dir
    ap.CONFIG_PATH = os.path.join(_new_dir, "config.json")
    ap.STATE_PATH = os.path.join(_new_dir, "state.json")
    ap.EVENTS_PATH = os.path.join(_new_dir, "events.jsonl")
    check("三個檔全部搬過來", ap._migrate_data_dir(), 3)
    check("設定內容沒跑掉",
          json.load(open(ap.CONFIG_PATH, encoding="utf-8"))["interval_min"], 60)
    # 複製不是搬移：遷移本身若有 bug，原始資料還在原地，不是只剩一份被寫壞的
    check("舊資料夾留著當備份",
          os.path.exists(os.path.join(_old_dir, "events.jsonl")), True)
    check("再跑一次不重覆搬", ap._migrate_data_dir(), 0)
    # 沙箱裡不能去撈使用者真實的資料夾。舊路徑是從現在的 DATA_DIR 同層推的，
    # 寫死絕對路徑的話，跑一次測試就會把真實紀錄複製進沙箱。
    _empty = tempfile.mkdtemp(prefix="wp_rename_empty_")
    ap.DATA_DIR = _empty
    ap.CONFIG_PATH = os.path.join(_empty, "config.json")
    check("同層沒有舊資料夾就安靜跳過", ap._migrate_data_dir(), 0)
    shutil.rmtree(_empty, ignore_errors=True)
finally:
    ap.DATA_DIR, ap.CONFIG_PATH, ap.STATE_PATH, ap.EVENTS_PATH = _keep
shutil.rmtree(_mig, ignore_errors=True)

print("\n8b. 測試自己不能碰到真實的設定檔")
# 這條是上面那個沙箱的看門狗。有人日後把沙箱拿掉、或在沙箱之前就 import，
# 這裡會立刻叫——而不是等使用者發現設定不見了。
real = os.path.join(os.environ.get("LOCALAPPDATA", ""), "WaterPet", "config.json")
check("CONFIG_PATH 指向沙箱", ap.CONFIG_PATH.startswith(SANDBOX), True)
check("沒有指到真實設定檔", os.path.normcase(ap.CONFIG_PATH) != os.path.normcase(real), True)

print("\n9. 改設定不能重置當前這一輪倒數（那是藏起來的 dismiss 後門）")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication(["app", "-platform", "offscreen"])
import island as isl  # noqa: E402

ISL_DIR = os.path.join(TMP, "island")
os.makedirs(ISL_DIR, exist_ok=True)
isl.DATA_DIR = ISL_DIR
isl.STATE_PATH = os.path.join(ISL_DIR, "state.json")
isl.EVENTS_PATH = os.path.join(ISL_DIR, "events.jsonl")

cfg = dict(ap.DEFAULTS)
cfg["daily_target_drinks"] = 7
# 深夜倍數在這裡要中性化，否則這支測試在 23:00-08:00 之間跑一定紅：
# _roll_interval() 會套用深夜倍數（30 × 1.45 = 44 分），而底下兩條斷言
# 寫死「30 分 ±15%」。它們要驗的是「新間隔要等下一輪才生效」，
# 跟深夜無關——把倍數設成 1.0 是移除無關變因，不是放寬標準。
cfg["late_night_ratio"] = 1.0
w = isl.Island(cfg)
for t in (w.tick_timer, w.frame, w.hold_timer, w.peek_timer):
    t.stop()
w.active_s = 1200.0
before_interval, before_active = w.interval_s, w.active_s

newer = dict(cfg)
newer["interval_min"] = 30
w.apply_config(newer)
check("間隔改了但這一輪不重擲", w.interval_s, before_interval)
check("累積的在電腦前時間不歸零", w.active_s, before_active)
check("新值有進去", w.cfg["interval_min"], 30)

# 下一次補水重擲時，新的間隔才生效
w.drink()
check("下一輪才套用新間隔（30 分 ±15%）",
      25 * 60 <= w.interval_s <= 35 * 60, True)

print("\n10. 設定變更要留痕（熱力圖要看得出那天標準換過）")
with open(isl.EVENTS_PATH, "r", encoding="utf-8") as f:
    evs = [json.loads(x) for x in f]
cfgev = [e for e in evs if e.get("event") == "config"]
check("有寫進事件紀錄", len(cfgev) >= 1, True)
check("記了改成什麼", cfgev[0]["changed"].get("interval_min"), 30)

print("\n11. 齒輪點得到，而且改設定會一路傳到島")
from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QLabel  # noqa: E402

import stats_window as sw  # noqa: E402

got = []
win = sw.StatsWindow(dict(cfg), isl.EVENTS_PATH, on_config=lambda c: got.append(c))
win.show()
win.frame.stop()

# 提示走自繪的 Tip，不走 QToolTip（理由見 stats_window.Tip 的 docstring）。
# 這兩條守的是「該有提示的地方真的掛了字」——沒有它，第 17 節驗的是一個
# 沒有人在用的元件。
_tips = [w._tip for w in win.findChildren(sw.Shields) + win.findChildren(sw.CupGauge)]
check("護盾與杯子都掛了提示", bool(_tips) and all(_tips), True)
check("而且不是走原生 tooltip",
      any(w.toolTip() for w in win.findChildren(sw.Graphic)), False)


def click(x, y):
    ev = QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(x, y),
                     Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    win.mousePressEvent(ev)


# 齒輪的中心：關閉鈕往左 GEAR_GAP。點它應該進設定，再點一次回紀錄。
gear_x = win.width() - sw.SHADOW - sw.WIN_PAD - 8 - sw.GEAR_GAP
gear_y = sw.SHADOW + sw.WIN_PAD + 14
check("預設在紀錄頁", win.mode, "stats")
click(gear_x, gear_y)
check("點齒輪進設定", win.mode, "settings")
click(gear_x, gear_y)
check("再點一次回紀錄", win.mode, "stats")

# 點齒輪不能誤觸關閉，也不能被誤判成拖曳
win._drag = None
click(gear_x, gear_y)
check("點齒輪不會啟動拖曳", win._drag, None)
check("點齒輪不會關掉視窗", win._closing, False)

# 改設定 -> 存檔 -> 回呼到島
win.settings_page.cfg["interval_min"] = 60
win.settings_page._emit()
check("設定變更有傳出去", bool(got), True)
check("傳出去的是新值", got[-1]["interval_min"], 60)

print("\n11b. 設定頁改的值要真的傳到島（含副作用）")
# 關鍵是視窗跟島共用同一份 cfg 的情況——實際執行時 island.show_stats()
# 就是把 self.cfg 直接傳進去的。上一版測試傳的是獨立字典，剛好繞過這個 bug：
# 視窗就地改掉島的字典 -> apply_config 比對「舊值」時舊值早就是新值 ->
# changed 是空的 -> 提早 return -> 換螢幕、改目標全部沒作用，也不留事件紀錄。
w2 = isl.Island(cfg)                       # cfg 是共用的那一份
for t in (w2.tick_timer, w2.frame, w2.hold_timer, w2.peek_timer):
    t.stop()
before_events = len([1 for _ in open(isl.EVENTS_PATH, encoding="utf-8")])
win2 = sw.open_window(w2.cfg, isl.EVENTS_PATH, None,
                      on_config=w2.apply_config, on_settings=True)
_app.processEvents()
check("視窗不能直接持有島的 cfg 物件", win2.cfg is w2.cfg, False)

idx = ap.INTERVAL_CHOICES.index(30)
win2.settings_page.interval.set_index(idx)
_app.processEvents()
check("島收到新的間隔", w2.cfg["interval_min"], 30)
after = [json.loads(x) for x in open(isl.EVENTS_PATH, encoding="utf-8")]
check("有留下 config 事件", any(e.get("event") == "config" and
                                 e.get("changed", {}).get("interval_min") == 30
                                 for e in after[before_events:]), True)
# 節奏類變更仍然不能重置當前這一輪
w2.drink()
check("下一輪才套用（30 分 ±15%）", 25 * 60 <= w2.interval_s <= 35 * 60, True)
win2.frame.stop()
win2.hide()

print("\n12. 換頁只重播卡片，不能把整個視窗淡掉再淡回來")
win._switch_mode("stats", animate=False)
win.sp_win.snap(1.0)
win.setWindowOpacity(1.0)
for c in win.cards:
    c.sp.snap(1.0)

win.seg.set_index(1)                     # 今天 -> 紀錄
check("換分頁後視窗維持不透明", win.sp_win.value, 1.0)

# 換過去的那一瞬間，新頁面的卡片必須已經是全透明的。
# 不是的話就代表「先換頁、後壓暗」，中間會被畫出一幀全亮的畫面——
# 使用者看到的是亮一下再淡入，也就是「閃一下」。
check("換頁瞬間新卡片已壓到透明",
      [round(c._fx.opacity(), 3) for c in win.cards],
      [0.0] * len(win.cards))
# 而且第一張要立刻開始淡入，不能排一個延遲計時器空在那裡
check("第一張卡沒有空窗期", win.cards[0].sp.target, 1.0)

win.sp_win.snap(1.0)
for c in win.cards:
    c.sp.snap(1.0)
win._switch_mode("settings")
check("進設定後視窗維持不透明", win.sp_win.value, 1.0)

# 開窗才該淡入整個視窗——那是唯一一次視窗真的從無到有
win.play_in()
check("開窗仍然從全透明淡入", win.sp_win.value, 0.0)

print("\n12b. 麵包屑：副標在設定模式下是一條寫著去處的返回連結")
win._switch_mode("settings", animate=False)
check("設定模式的副標是麵包屑", win.sub_lbl.text(), "‹ 喝水紀錄")
win.sub_lbl.clicked.emit()
check("點麵包屑會回紀錄", win.mode, "stats")
check("紀錄模式副標換回資訊", win.sub_lbl.text().startswith("每日目標"), True)

print("\n12c. 清除紀錄要跳 popup，而且刪除鍵不能長在觸發鍵的位置")
from PySide6.QtCore import QRect  # noqa: E402

fired = []
win._switch_mode("settings", animate=False)
_app.processEvents()
win.settings_page.reset_done.connect(lambda: fired.append(1))
check("一開始沒有 popup", win._confirm, None)

win.settings_page.danger.action.clicked.emit()
_app.processEvents()
ov = win._confirm
check("按下清除紀錄會開 popup", ov.isVisible(), True)
check("遮罩蓋滿整個視窗", ov.size(), win.size())

# 這一條是這次改版的理由，不是裝飾。舊版就地確認時，「刪除」與「清除紀錄」
# 水平重疊 33px，兩顆又都靠右對齊——手快點兩下、或第一下以為沒反應再補一下，
# 第二下就落在「刪除」上，而清除紀錄不可復原。
# 釘住「兩者不得相交」，之後任何人把確認搬回原地都會在這裡被擋下來。
trig = win.settings_page.danger.action
tg = QRect(trig.mapTo(win, QPoint(0, 0)), trig.size())
cf = QRect(ov.card.mapTo(win, ov.confirm.geometry().topLeft()), ov.confirm.size())
check("刪除鍵與觸發鍵完全不重疊", tg.intersects(cf), False)

check("開著的時候還沒刪", fired, [])
ov.cancel.clicked.emit()
check("取消會關掉 popup", ov.isVisible(), False)
check("取消後沒刪", fired, [])

# 點卡片外面也是取消。誤觸要落在安全的那一邊，所以外面只認取消不認確認。
win.settings_page.danger.action.clicked.emit()
_app.processEvents()
ov = win._confirm
ov.mousePressEvent(QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(4, 4),
                               Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
check("點卡片外面＝取消", ov.isVisible(), False)
check("點外面沒刪", fired, [])

win.settings_page.danger.action.clicked.emit()
_app.processEvents()
win._confirm.confirm.clicked.emit()
check("按刪除才真的執行", fired, [1])
check("執行後 popup 收起來", win._confirm.isVisible(), False)

print("\n12d. 網格：列高只能是宣告過的三種，控制項中心線才會對齊")
win._switch_mode("settings", animate=False)
allowed = {sw.ROW_TALL, sw.ROW_FLAT, sw.ROW_INFO, sw.ROW_SECTION}
bad = []
for card in win.settings_page.cards:
    box = card.box
    for i in range(box.count()):
        wd = box.itemAt(i).widget()
        if wd is None or isinstance(wd, (sw.Divider, sw.Label, sw.DangerRow)):
            continue
        if isinstance(wd, QLabel):        # para() 產的自動換行段落，高度由內容決定
            continue
        if wd.height() not in allowed:
            bad.append((type(wd).__name__, wd.height()))
check(f"所有設定列高度屬於 {sorted(allowed)}", bad, [])

print("\n12e. 從系統匣直接開「設定」，版面不能塌掉")
# 這條路徑（open_window(on_settings=True)）先前是壞的：QStackedWidget 會把
# 非當前頁 hide 掉，而 layout 對 hidden 的 widget 一律回報 sizeHint 0——
# 在設定模式下量紀錄那一側會量到 64px，視窗縮成 277、卡片壓成 13px、文字疊在一起。
# 渲染測試一直是綠的，因為它們都是「先開紀錄再切設定」，剛好繞過這條路。
direct = sw.open_window(dict(cfg), isl.EVENTS_PATH, on_settings=True)
_app.processEvents()
normal = sw.open_window(dict(cfg), isl.EVENTS_PATH)
_app.processEvents()
check("直接開設定的高度 == 直接開紀錄的高度", direct.height(), normal.height())
check("開起來就停在設定頁", direct.mode, "settings")
# 設定頁現在可捲動，所以不再要求「塞得進內容區」。真正該守的是沒有一張卡被壓扁——
# 那是版面塌掉時的症狀，跟捲不捲動無關。
# 不拿 sizeHint 當基準：自動換行的 QLabel 在寬度未定時會多報高度，
# 拿它比會誤判。版面塌掉時的症狀很極端（實測卡片被壓成 13px），
# 用一個絕對下限就抓得到，也不會被換行的估算誤差影響。
squashed = [(i, c.height()) for i, c in enumerate(direct.settings_page.cards)
            if c.height() < 80]
check("沒有卡片被壓扁", squashed, [])
check("內容比可視區高，捲軸有東西可捲",
      direct.pane.area.verticalScrollBar().maximum() > 0, True)
check("進來時停在頂端", direct.pane.area.verticalScrollBar().value(), 0)
for _w in (direct, normal):
    _w.frame.stop()
    _w.hide()

print("\n12f. 捲動區不能是透明的洞（會讓滑鼠穿透到底下的視窗）")
# 視窗開了 WA_TranslucentBackground，而 Windows 上完全透明的像素會讓點擊穿透。
# 捲動區的視口若不填背景，那一整塊就變成洞：看起來透明、點下去操作到底下的瀏覽器。
# 這個 bug 離線渲染抓不到——grab() 不經過視窗合成，洞在圖裡是實心的，
# 所以只能從屬性上檢查。
from PySide6.QtGui import QImage  # noqa: E402


def transparent_points(win):
    """數視窗本體內有多少取樣點是半透明的。

    直接量 alpha，不從屬性推。屬性檢查只能證明「我設了某個旗標」，
    證明不了「畫面上真的有東西」——第一版就是設了旗標、測試綠燈，
    但 setViewport() 交出去的自繪視口其 paintEvent 根本沒被呼叫，實際 alpha 全 0。
    """
    img = win.grab().toImage().convertToFormat(QImage.Format_ARGB32)
    s = sw.SHADOW + 4          # 往內縮一點，避開本來就該透明的圓角
    return sum(1 for y in range(s, win.height() - s, 2)
               for x in range(s, win.width() - s, 2)
               if (img.pixel(x, y) >> 24) < 200)


direct._switch_mode("stats", animate=False)
_app.processEvents()
base = transparent_points(direct)
direct._switch_mode("settings", animate=False)
_app.processEvents()
got = transparent_points(direct)
print(f"       紀錄頁 {base} 點 / 設定頁 {got} 點")
# 設定頁不該比紀錄頁破更多洞。修正前是 98997 對 1216。
check("設定頁沒有比紀錄頁多出透明區塊", got <= base + 8, True)

print("\n12g. 換主題要連視窗外框一起換")
# 標題與副標是 QLabel，顏色寫在建立當下的 stylesheet 裡，重建設定頁不會動到它們。
# 漏掉的話：切到淺色底色變白，標題還留著深色主題的淺色文字，等於消失。
before = direct.title_lbl.styleSheet()
direct._on_theme_changed("light")
_app.processEvents()
after = direct.title_lbl.styleSheet()
check("標題顏色跟著主題換", after != before, True)
check("淺色主題的標題是深色文字", "28,28,30" in after, True)
direct._on_theme_changed("dark")
_app.processEvents()
check("切回深色也要換回來", "235,235,245" in direct.title_lbl.styleSheet(), True)

print("\n12h. 滾輪走彈簧，不是一格一格跳")
pane = direct.pane
bar = pane.area.verticalScrollBar()
bar.setValue(0)
pane._sp.snap(0.0)
from PySide6.QtGui import QWheelEvent  # noqa: E402

# 事件要送到 QScrollArea——QAbstractScrollArea 自己處理 wheel，不會往上傳給
# ScrollPane。第一版把 wheelEvent 寫在 ScrollPane 上，一次都沒被呼叫過。
pane.area.wheelEvent(QWheelEvent(QPointF(100, 100), QPointF(100, 100),
                                 QPoint(0, -120), QPoint(0, -120),
                                 Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False))
check("滾一格會設定一個目標", pane._sp.target > 0, True)
check("但畫面還沒瞬間跳過去", bar.value(), 0)
for _ in range(60):
    pane._last -= 0.016
    pane._step()
check("彈簧會把它補到目標", abs(bar.value() - pane._sp.target) <= 1, True)

print("\n12i. 卡片高度要剛好，不能多也不能少（視窗可以被拉寬拉窄）")
# QVBoxLayout 不會把 heightForWidth 可靠地往下傳。「關於」卡裡有會換行的段落，
# 實測版面的 sizeHint 比 heightForWidth 多 66px，而空間是照前者分配的：
# 多出來的塞給「顯示」卡（兩張卡中間憑空多一大塊空白），需要更高時又不給
# （段落被切掉）。使用者兩個都遇到了，回報「跑掉了」。
#
# 視窗可以拖曳縮放，所以要在好幾個寬度上驗，不能只驗預設值。
#
# 用自己的視窗，而且保持顯示中：隱藏的視窗不會重排，拿它量會量到上一次
# 的殘值（第一版沿用 12e 那個已經 hide() 掉的視窗，卡片永遠停在 318）。
fit_win = sw.open_window(dict(cfg), isl.EVENTS_PATH, on_settings=True)
fit_win.frame.stop()
_app.processEvents()

bad_fit = []
for w in (900, 840, 780, 720, 660):
    fit_win.resize(w, fit_win.height())
    _app.processEvents()
    for i, card in enumerate(fit_win.settings_page.cards):
        lay = card.layout()
        need = (lay.heightForWidth(card.width()) if lay.hasHeightForWidth()
                else max(lay.sizeHint().height(), lay.minimumSize().height()))
        if card.height() != need:
            bad_fit.append(f"寬 {w} 的卡 {i}：給 {card.height()} 需要 {need}")
check("每個寬度下卡片高度都剛好等於需要的", bad_fit[:4], [])

# 卡與卡之間只能是宣告的那個間距。多出來就是有卡被拉伸了。
fit_win.resize(840, fit_win.height())
_app.processEvents()
lay = fit_win.settings_page.layout()
gaps, prev = [], None
for i in range(lay.count()):
    widget = lay.itemAt(i).widget()
    if widget is None or not isinstance(widget, sw.Card):
        continue
    if prev is not None:
        gaps.append(widget.geometry().top() - prev)
    prev = widget.geometry().bottom()
check("卡與卡之間就是宣告的間距", {g - 1 for g in gaps}, {sw.GAP})
fit_win.hide()

print("\n13. 設定頁的高度必須跟紀錄頁一樣，換頁時視窗不能跳動")
win2 = sw.StatsWindow(dict(cfg), isl.EVENTS_PATH)
win2.show()
win2.frame.stop()
h_stats = win2.height()
win2._switch_mode("settings", animate=False)
h_settings = win2.height()
check("兩種模式同高", h_settings, h_stats)

print("\n14. 防線：只有真的程式可以寫真實資料檔")
# 上面 8b 那條看門狗只驗「路徑有沒有指到沙箱」，擋不住忘了設路徑的新測試。
# 這一條驗的是程式裡的防線本身有沒有在運作。
_probe = []
try:
    ap.guard_real_write(os.path.join(os.environ.get("LOCALAPPDATA", ""),
                                     "WaterPet", "config.json"))
except RuntimeError as exc:
    _probe.append(str(exc))
check("未舉手寫真實設定會拋例外", bool(_probe), True)
check("沙箱路徑照樣放行", ap.guard_real_write(ap.CONFIG_PATH), None)
# Qt 會吞掉 slot 裡的例外（只印 traceback 就繼續跑），所以要能事後斷言。
# 扣掉上面那一次故意的探測，這支測試不該再攔到任何東西。
check("除了故意探測那次，沒有其他攔截",
      len(ap.real_write_violations()), len(_probe))

print("\n15. 護盾的說明：講「再達標幾天」，不講日期")
# 這一列的右邊走過三個版本（消耗的日期、補滿的日期、一顆 ⓘ），最後全部拿掉，
# 說明掛在圖示上。護盾會自己運作，不知道細節不影響任何事。
import stats_window as _sw  # noqa: E402


def _tipdata(left, total=2, nxt=1):
    return {"today_key": "2026-08-16",
            "streak": {"saved_days": [], "saves_left": left,
                       "saves_total": total, "saves_next_in": nxt}}


check("用完了要講怎麼賺回來", _sw._saves_tip(_tipdata(0, nxt=2)),
      "還剩 0 個，再達標 2 天多一個")
check("少一個也一樣", _sw._saves_tip(_tipdata(1, nxt=1)),
      "還剩 1 個，再達標 1 天多一個")

# 存滿就沒有要補的東西，不講數字。但也不留空白——這一頁是動機的介面，
# 護盾全滿本來就值得被拍拍肩膀。
check("存滿時給一句話而不是數字", _sw._saves_tip(_tipdata(2)), "保持水分！")

# **不能寫成日期。** 護盾靠達標賺回來，不靠時間流逝，寫「9月1日補滿」會暗示
# 只要等就會回來——那是假的。
for _n in (0, 1):
    check(f"剩 {_n} 個時不出現日期",
          any(c in _sw._saves_tip(_tipdata(_n)) for c in "月號"), False)

print("\n16. 引導不能悄悄改掉使用者原本的設定")
# 引導按下「開始」會把開關的值寫回設定（_emit_finish -> _onboarding_done）。
# 所以任何一個寫死在 OnboardWindow 裡的預設值，都會在「再看一次」的路徑上
# 把使用者原本的設定改掉——而那幾個開關在第四、五頁，一路按「下一步」
# 根本不會注意到。
#
# 自啟就是這樣漏掉的：它一度寫死 Toggle(True)。
import onboard as _ob  # noqa: E402

# 絕對不要讓這一節碰到真的登錄檔。show_onboarding() 會呼叫 autostart_enabled()，
# 而我們要驗的正是「它有沒有被讀進去」，不是「這台機器現在設什麼」。
_real_enabled = ap.autostart_enabled
_fake_enabled = [False]
ap.autostart_enabled = lambda: _fake_enabled[0]

_w = _ob.OnboardWindow(autostart=False, sound_on=False)
_w.frame.stop()
check("帶什麼進去，開關就是什麼", _w.autostart.on, False)
_got = {}
_w.finished.connect(_got.update)
_w._emit_finish()
check("按下開始吐出的就是開關當下的值", _got["autostart"], False)
check("音效同一條路", _got["sound_enabled"], False)
_w.close()

# 呼叫端的分流：第一次給建議值（開），重看給現況。
# 直接驗 show_onboarding() 傳了什麼，不去戳 open_window 的內部。
_passed = {}
_ob_open = _ob.open_window
_ob.open_window = lambda *a, **k: _passed.update(k) or None

_isl_w = isl.Island(dict(isl.DEFAULT_CONFIG))
_isl_w.tick_timer.stop(); _isl_w.frame.stop()
_isl_w.hold_timer.stop(); _isl_w.peek_timer.stop()

_fake_enabled[0] = False
_isl_w.show_onboarding(first_run=True)
check("第一次啟動一律建議開著（登錄檔那時本來就是空的）",
      _passed["autostart"], True)

_isl_w.show_onboarding(first_run=False)
check("重看導覽帶現況：關著的就是關著", _passed["autostart"], False)
_fake_enabled[0] = True
_isl_w.show_onboarding(first_run=False)
check("重看導覽帶現況：開著的就是開著", _passed["autostart"], True)

_ob.open_window = _ob_open
ap.autostart_enabled = _real_enabled

# 作息那兩個步進器：只有真的動過才算「手動」。
#
# 先前 _emit_finish() 無條件寫 True，理由是「他剛剛親口回答過」。但被問到跟
# 回答了是兩件事——一路按「下一步」的人從頭到尾沒碰過那兩個數字，而他正是
# 最需要自動推導的那一種。重看導覽更明顯：本來自動的人走一遍就被改成手動。
for _label, _kw, _move, _want_wake, _want_bed in (
        ("第一次沒碰", dict(wake=8, bedtime=0), None, False, False),
        ("第一次調了起床", dict(wake=8, bedtime=0), 10, True, False),
        ("重看，本來手動", dict(wake=10, bedtime=2, wake_manual=True,
                                bedtime_manual=True), None, True, True),
        ("重看，本來自動", dict(wake=9, bedtime=1), None, False, False)):
    _w3 = _ob.OnboardWindow(**_kw)
    _w3.frame.stop()
    if _move is not None:
        _w3.wake_pick.set_hour(_move)
    _r3 = {}
    _w3.finished.connect(_r3.update)
    _w3._emit_finish()
    check(f"{_label}：起床", _r3["wake_manual"], _want_wake)
    check(f"{_label}：就寢", _r3["bedtime_manual"], _want_bed)
    _w3.close()

print("\n17. 自繪的提示泡泡")
sw_qt_flag = _sw.Qt.WindowTransparentForInput
# 原生 QToolTip 有兩個改不掉的問題：要等將近一秒，而且是方角系統字的補丁。
# 換成自繪之後這一節守的是它不能又長回那些毛病。
_tip = _sw.Tip._instance()
check("同一顆，不會冒出第二個", _sw.Tip._instance() is _tip, True)

# 這一條是這個元件唯一真的難查的地方。頂層視窗光靠 WA_TransparentForMouseEvents
# 沒有用（那是給子元件的），少了 WindowTransparentForInput，泡泡會在作業系統
# 那一層接走滑鼠——症狀是第一個提示出得來、之後整個視窗再也不出現任何提示，
# 而且連原本正常的那個再滑一次也啞掉。
check("頂層視窗對輸入是穿透的",
      bool(_tip.windowFlags() & sw_qt_flag), True)
check("Qt 內部也跳過它",
      _tip.testAttribute(_sw.Qt.WA_TransparentForMouseEvents), True)
check("不搶焦點", _tip.testAttribute(_sw.Qt.WA_ShowWithoutActivating), True)

_probe_w = _sw.Shields(2, 2, "測試用的字")
_probe_w.resize(76, 36)
_probe_w.show()
_app.processEvents()
_sw.Tip.show_for(_probe_w, "兩行\n的提示")
check("顯示出來", _tip.isVisible(), True)
check("文字進去了", _tip._text, "兩行\n的提示")
_h1 = _tip.height()
_sw.Tip.show_for(_probe_w, "一行")
check("換成一行會變矮（高度跟著內容算）", _tip.height() < _h1, True)
_sw.Tip.hide_tip()
check("收得起來", _tip.isVisible(), False)

# 空字串不該冒出一個空泡泡
_sw.Tip.show_for(_probe_w, "")
check("沒有內容就不顯示", _tip.isVisible(), False)

_probe_w.deleteLater()

# 視窗收起來時提示要跟著走。它是獨立的頂層視窗，不會自動被帶走——留在螢幕上
# 就是一塊擦不掉的字，而且底下的視窗已經不見了，使用者沒辦法讓它消失。
#
# 這一條特別容易漏：`Graphic.hideEvent` 看起來已經涵蓋了，其實沒有——
# Qt 只對「自己被隱藏」的元件送 Hide，父層被隱藏時子元件收到的是 HideToParent。
_hidden = []
_orig_hide = _sw.Tip.hide_tip
_sw.Tip.hide_tip = classmethod(lambda cls: (_hidden.append(1), _orig_hide())[1])

_w2 = sw.StatsWindow(dict(cfg), isl.EVENTS_PATH)
_w2.show(); _w2.frame.stop()
_app.processEvents()
_hidden.clear()
_w2.hide()
_app.processEvents()
check("視窗收起來時會叫 hide_tip", bool(_hidden), True)
_hidden.clear()
_w2.close()
check("按下關閉時也會", bool(_hidden), True)
_sw.Tip.hide_tip = _orig_hide
_w2.deleteLater()

print("\n18. 作息可以從手動改回自動")# 使用者的話：「我都設定 02:00/10:00，但最近比較早起，可是看到設定不一樣會有點煩」。
# 手動設過的值不會跟著生活變，而先前沒有任何一條路可以改回自動——
# `*_manual` 一旦是 True 就永遠是 True，只能去改 config.json。
# 設定進得去出不來，那不是設定，是單向門。
_c = dict(cfg)
_c.update({"wake_manual": True, "bedtime_manual": True,
           "day_rollover_hour": 10, "bedtime_hour": 2})
_p = _sw.SettingsPage(_c)
check("手動時說明要標出來", "手動指定" in _p._wake_text(), True)
check("就寢那一列也標", "手動指定" in _p._late_text(), True)
check("手動時才出現「改為自動」", _p.wake_auto.isVisibleTo(_p), True)

_p._back_to_auto("wake")
check("按下去就交還給推導", _p.cfg["wake_manual"], False)
check("說明跟著改", "手動指定" in _p._wake_text(), False)
check("連結跟著收起來", _p.wake_auto.isVisibleTo(_p), False)
# 這一條是最容易寫錯的地方：同步步進器時若發訊號，_on_wake 會把旗標又設回
# True，於是「改為自動」按下去等於沒按。
check("同步步進器不能把旗標又設回手動", _p.cfg["wake_manual"], False)

# 起床那一列的說明不能再寫「次數將於每日重置」——換日已經訂死在早上 5 點
# （settings.DAY_ROLLOVER_HOUR），這一列跟次數重置沒有關係了。
check("起床那一列不再宣稱自己管重置",
      "重置" in _p._wake_text(), False)
check("而且講得出它現在管什麼", "夜間" in _p._wake_text(), True)

print("\n19. 公式的性質（窮舉，不是抽樣）")
# 第 1 節只驗了 6 個點，而那 6 個期望值是人自己寫上去的——公式的假設要是錯的，
# 那 6 項會照著錯的假設一起通過。這一節改成掃過使用者能輸入的整個範圍，
# 驗的是「不管餵什麼都必須成立」的性質，不依賴任何一個手寫的期望值。
#
# 體重的範圍就是輸入框驗證器的範圍（QIntValidator(30, 200)）。
_WEIGHTS = range(30, 201)
_MLS = range(50, 601, 10)
_bad_range = _bad_up = _bad_down = None
for _ml in _MLS:
    _prev = None
    for _kg in _WEIGHTS:
        _t = ap.target_from_weight(_kg, _ml)
        if _bad_range is None and (not isinstance(_t, int)
                                   or not ap.TARGET_MIN <= _t <= ap.TARGET_MAX):
            _bad_range = f"kg={_kg} ml={_ml} -> {_t!r}"
        if _bad_up is None and _prev is not None and _t < _prev:
            _bad_up = f"ml={_ml} kg={_kg}: {_prev} -> {_t}"
        _prev = _t
for _kg in _WEIGHTS:
    _prev = None
    for _ml in _MLS:
        _t = ap.target_from_weight(_kg, _ml)
        if _bad_down is None and _prev is not None and _t > _prev:
            _bad_down = f"kg={_kg} ml={_ml}: {_prev} -> {_t}"
        _prev = _t
print(f"       掃過 {len(_WEIGHTS) * len(_MLS)} 組（{len(_WEIGHTS)} 種體重 × {len(_MLS)} 種單次水量）")
check("一律是 4~12 的整數", _bad_range, None)
# 「越重反而喝越少」是實際收到的使用者回報。公式本身不會這樣，但改壞了會。
check("體重越重，次數不會變少", _bad_up, None)
check("單次喝越多，次數不會變多", _bad_down, None)

print("\n20. 設定檔被手改成怪值時不能讓程式開不起來")
# config.json 是純文字，使用者改得到，而說明本身就在教人改它（單次水量沒上面板）。
# 手改最常見的失誤是多加引號：JSON 讀進來是字串，kg * 30 變成字串重複 30 次。
#
# 這條例外炸得起來的位置特別糟：effective_target() 在 island.main() 裡、
# **建立動態島之前**被呼叫，那一行沒有 try。一個引號就讓整個程式開不起來，
# 而使用者只會看到「點了圖示什麼都沒發生」。
# 2026-08-19 在沙箱用真的設定檔重現過，這一節是它的守門人。
_JUNK = [
    ("體重是字串", {"weight_kg": "65"}),
    ("體重是亂碼", {"weight_kg": "abc"}),
    ("體重是 True", {"weight_kg": True}),
    ("體重是 list", {"weight_kg": [65]}),
    ("體重是負數", {"weight_kg": -50}),
    ("單次水量是字串", {"weight_kg": 65, "ml_per_drink_estimate": "200"}),
    ("單次水量是 0", {"weight_kg": 65, "ml_per_drink_estimate": 0}),
    ("單次水量是亂碼", {"weight_kg": 65, "ml_per_drink_estimate": "x"}),
    ("手動目標是字串", {"target_manual": True, "daily_target_drinks": "8"}),
    ("手動目標是亂碼", {"target_manual": True, "daily_target_drinks": "x"}),
    ("手動目標超出上限", {"target_manual": True, "daily_target_drinks": 999}),
]
_junk_bad = None
for _label, _cfg in _JUNK:
    try:
        _r = ap.effective_target(_cfg)
    except Exception as _e:                                   # noqa: BLE001
        _junk_bad = f"{_label} 讓程式當掉：{type(_e).__name__}"
        break
    if not isinstance(_r, int) or not ap.TARGET_MIN <= _r <= ap.TARGET_MAX:
        _junk_bad = f"{_label} 回傳了 {_r!r}"
        break
check(f"{len(_JUNK)} 種怪值都不當機、都回合法次數", _junk_bad, None)
# 看得懂的字串要接住，不要當成沒填——使用者寫 "65" 的意思就是 65。
check("\"65\" 當成 65", ap.effective_target({"weight_kg": "65"}), 7)
check("\"8\" 當成手動指定 8 次",
      ap.effective_target({"target_manual": True, "daily_target_drinks": "8"}), 8)

shutil.rmtree(SANDBOX, ignore_errors=True)
print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 項失敗：{fails}"))
sys.exit(1 if fails else 0)

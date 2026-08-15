# -*- coding: utf-8 -*-
"""驗證 settings.py：體重推導、作息推導、鍵名升級、舊檔遷移、熱套用不重置倒數。"""
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, r"E:\Claude Project\Claude Inbox\喝水提醒桌寵")

import settings as ap  # noqa: E402

# ---------------------------------------------------------------- 沙箱
# **這段一定要在任何測試之前。**
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

print("\n4. 作息推導：找最長的一段沒在用電腦的時間")
# 造一份「每天 09:00-23:00 在電腦前」的紀錄：安靜段是 00:00-08:00，起點 0
base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
rows = []
for d in range(6):
    for h in range(9, 24):
        rows.append((base + timedelta(days=d, hours=h), "drink"))
p = write_events(rows)
check("換日設在安靜段起點", ap.infer_schedule(p)[0], 0)
check("深夜模式是換日往前 6 小時", ap.infer_schedule(p)[1], 18)

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
check("day_start 不影響推導", ap.infer_schedule(write_events(noise))[0], 0)

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

import stats_window as sw  # noqa: E402

got = []
win = sw.StatsWindow(dict(cfg), isl.EVENTS_PATH, on_config=lambda c: got.append(c))
win.show()
win.frame.stop()


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

print("\n12. 換頁只重播卡片，不能把整個視窗淡掉再淡回來")
win._switch_mode("stats", animate=False)
win.sp_win.snap(1.0)
win.setWindowOpacity(1.0)
for c in win.cards:
    c.sp.snap(1.0)

win.seg.set_index(1)                     # 今天 -> 紀錄
check("換分頁後視窗維持不透明", win.sp_win.value, 1.0)
check("換分頁有重播卡片", all(c.sp.target == 0.0 or c.sp.value < 1.0
                              for c in win.cards), True)

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

print("\n12c. 清除紀錄要兩段：先問「確定要刪除嗎」，確認了才真的刪")
fired = []
d = sw.DangerAction("說明", "確定要清除所有紀錄嗎？")
d.confirmed.connect(lambda: fired.append(1))
check("預設不是待確認狀態", d._armed, False)
check("預設看不到確認文字", d.prompt_lbl.isVisible(), False)
d.action.clicked.emit()                    # 點「清除紀錄」
check("點一下只是進入確認", d._armed, True)
check("還沒真的刪", fired, [])
d.cancel.clicked.emit()
check("可以取消", d._armed, False)
check("取消後沒刪", fired, [])
d.action.clicked.emit()
d.confirm.clicked.emit()                   # 點「刪除」
check("確認後才刪", fired, [1])
check("刪完收回確認狀態", d._armed, False)

print("\n12d. 網格：列高只能是宣告過的三種，控制項中心線才會對齊")
win._switch_mode("settings", animate=False)
allowed = {sw.ROW_TALL, sw.ROW_FLAT, sw.ROW_INFO, sw.ROW_SECTION}
box = win.settings_page.card.box
bad = []
for i in range(box.count()):
    wd = box.itemAt(i).widget()
    if wd is None or isinstance(wd, (sw.Divider, sw.Label)):
        continue
    if wd.height() not in allowed:
        bad.append((i, wd.height()))
check(f"所有設定列高度屬於 {sorted(allowed)}", bad, [])

print("\n13. 設定頁的高度必須跟紀錄頁一樣，換頁時視窗不能跳動")
win2 = sw.StatsWindow(dict(cfg), isl.EVENTS_PATH)
win2.show()
win2.frame.stop()
h_stats = win2.height()
win2._switch_mode("settings", animate=False)
h_settings = win2.height()
check("兩種模式同高", h_settings, h_stats)
check("設定頁內容放得下",
      win2.settings_page.sizeHint().height() <= win2.root.height(), True)

shutil.rmtree(SANDBOX, ignore_errors=True)
print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 項失敗：{fails}"))
sys.exit(1 if fails else 0)

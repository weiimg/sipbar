# -*- coding: utf-8 -*-
"""驗證正式版動態島：計時、閒置暫停、升級、達標、換日、暫停、統計、顯示與隱藏。"""
import os
import shutil
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import island as isl  # noqa: E402

TEST_DIR = os.path.join(SCRATCH, "wp_island")
shutil.rmtree(TEST_DIR, ignore_errors=True)
isl.DATA_DIR = TEST_DIR
isl.STATE_PATH = os.path.join(TEST_DIR, "state.json")
isl.EVENTS_PATH = os.path.join(TEST_DIR, "events.jsonl")

IDLE = [0.0]
isl.idle_seconds = lambda: IDLE[0]

from datetime import datetime, timedelta  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
cfg = dict(isl.DEFAULT_CONFIG)
cfg["tick_seconds"] = 60          # 一 tick 當一分鐘，快轉用
w = isl.Island(cfg)
w.tick_timer.stop()
w.frame.stop()
w.hold_timer.stop()

fails = []


def check(label, got, want):
    ok = got == want
    print(("  ok  " if ok else "  FAIL") + f"  {label}: {got!r}" + ("" if ok else f"  (預期 {want!r})"))
    if not ok:
        fails.append(label)


def ticks(n):
    for _ in range(n):
        w.tick()


def settle_springs():
    """把彈簧直接推到目標，跳過動畫時間。"""
    for s in (w.sp_expand, w.sp_reveal, w.sp_content):
        s.value, s.velocity = s.target, 0.0


interval_min = w.interval_s / 60
print(f"\n[本次間隔 {interval_min:.1f} 分鐘，深夜模式={'是' if w._is_late() else '否'}]")

print("\n1. 起始應該是隱藏的")
check("狀態", w.state, isl.NORMAL)
check("reveal 目標", w.sp_reveal.target, 0.0)

print("\n2. 還沒到時間不該出現")
ticks(int(interval_min) - 2)
check("狀態", w.state, isl.NORMAL)
check("reveal 目標", w.sp_reveal.target, 0.0)

print("\n3. 到時間 -> 口渴、滑下來、展開")
ticks(3)
check("狀態", w.state, isl.THIRSTY)
check("reveal 目標", w.sp_reveal.target, 1.0)
check("expand 目標", w.sp_expand.target, 1.0)

print("\n4. 停留結束 -> 縮到 0.35，但不消失")
w._settle()
check("expand 目標", w.sp_expand.target, 0.35)
check("reveal 目標（仍現身）", w.sp_reveal.target, 1.0)

# 閒置秒數要從設定值推，不能寫死。寫死 20 分的版本在門檻從 15 調成 30 那天
# 整組垮掉（active_s 照跑、狀態一路升級），而失敗訊息看起來像狀態機壞了，
# 跟真正的原因差很遠。
_idle_min = cfg["idle_threshold_min"] + 5
print(f"\n5. 離開電腦時計時停住（閒置 {_idle_min} 分，跑 30 tick 不該升級）")
IDLE[0] = _idle_min * 60
before = w.active_s
ticks(30)
check("active_s 沒增加", w.active_s, before)
check("狀態沒變", w.state, isl.THIRSTY)
IDLE[0] = 0.0

print("\n6. 回到電腦前，忽略 15 分 -> 虛弱")
ticks(cfg["escalate_weak_min"] + 1)
check("狀態", w.state, isl.WEAK)
w._settle()
check("停留尺寸", w.sp_expand.target, 0.50)

print("\n7. 忽略到 40 分 -> 倒地，且不收合不消失")
ticks(cfg["escalate_collapsed_min"] - cfg["escalate_weak_min"] + 1)
check("狀態", w.state, isl.COLLAPSED)
w._settle()
check("expand 目標（不收合）", w.sp_expand.target, 1.0)
check("reveal 目標（不消失）", w.sp_reveal.target, 1.0)

print("\n8. 喝了 -> 閃確認訊息，然後滑走消失")
w.drink()
check("狀態", w.state, isl.SATISFIED)
check("次數", w.drinks, 1)
check("active_s 歸零", w.active_s, 0.0)
check("訊息", w.message, f"喝了，還剩 {cfg['daily_target_drinks'] - 1} 次")
w._settle()                      # 模擬閃爍時間結束
check("狀態", w.state, isl.NORMAL)
check("reveal 目標（消失）", w.sp_reveal.target, 0.0)

print("\n9. 補滿 6 次 -> 達標訊息，之後整天不再出現")
for _ in range(cfg["daily_target_drinks"] - 1):
    w.drink()
check("次數", w.drinks, cfg["daily_target_drinks"])
check("訊息", w.message, "今天達標了")
check("達標時小標顯示連續", w.sub_message.startswith("連續 ") or w.streak == 0, True)
w._settle()
ticks(600)
check("跑 600 分鐘仍隱藏", w.sp_reveal.target, 0.0)
check("狀態", w.state, isl.NORMAL)

print("\n10. 換日 -> 次數歸零、重新開始")
w.day = "1999-01-01"
w.tick()
check("次數", w.drinks, 0)
check("狀態", w.state, isl.NORMAL)

print("\n11. 暫停 2 小時期間不出現")
w.pause_2h()
ticks(600)
check("狀態", w.state, isl.NORMAL)
check("reveal 目標", w.sp_reveal.target, 0.0)
w._cancel_pause()

print("\n12. 存檔與統計")
w._persist()
saved = isl.load_state()
check("存檔鍵", sorted(saved.keys()),
      ["active_s", "day", "drinks", "interval_s", "paused_until", "saved_ts",
       "state"])
text = isl.build_stats_text(cfg)
print("     " + text.replace("\n", "\n     "))
check("統計有內容", "提醒" in text, True)

print("\n12b. 視窗要容得下藥丸＋擠壓＋陰影，否則圓角會被視窗邊界切掉")
settle_springs()
w.state = isl.THIRSTY
w.sp_expand.value = w.sp_expand.target = 1.0
w.sp_expand.velocity = 2.0                 # 製造最大的擠壓拉伸
w.sp_reveal.value = w.sp_reveal.target = 1.0
r = w.pill_rect()
check("藥丸左緣沒有超出視窗", r.left() - isl.PILL_SHADOW >= 0, True)
check("藥丸右緣沒有超出視窗", r.right() + isl.PILL_SHADOW <= isl.WIN_W, True)
check("藥丸底部沒有超出視窗", r.bottom() + 12 <= isl.WIN_H, True)
print(f"       視窗 {isl.WIN_W}x{isl.WIN_H}　藥丸 x in [{r.left():.0f}, {r.right():.0f}] "
      f"底部 {r.bottom():.0f}（含擠壓）")
w.sp_expand.velocity = 0.0

print("\n12c. 遮罩要涵蓋陰影，不然陰影會被裁掉")
w._apply_mask()
mask = w.mask().boundingRect()
r = w.pill_rect()
check("遮罩左側涵蓋陰影", mask.left() <= r.left() - isl.PILL_SHADOW, True)
check("遮罩右側涵蓋陰影", mask.right() >= r.right() + isl.PILL_SHADOW, True)
check("遮罩下方涵蓋陰影", mask.bottom() >= r.bottom() + 10, True)
# 藥丸寬度常態是小數（pulse 與內容插值），右緣的整數化最容易差 1px，
# 失敗時要一眼看得出是差在捨入還是差在邊界值。
print(f"       藥丸 x in [{r.left():.2f}, {r.right():.2f}]　"
      f"遮罩 x in [{mask.left()}, {mask.right()}]　需要 >= {r.right() + isl.PILL_SHADOW:.2f}")

print("\n13. 遮罩只涵蓋藥丸，不擋整條標題列")
settle_springs()
w.state = isl.NORMAL
w.sp_expand.value = w.sp_expand.target = 0.0
w.sp_reveal.value = w.sp_reveal.target = 1.0
w._apply_mask()
mask_w = w.mask().boundingRect().width()
# 遮罩＝藥丸＋兩側陰影。意圖是「不要擋住整條標題列」，不是一個固定數字。
limit = isl.PILL_MIN[0] + (isl.PILL_SHADOW + 1) * 2 + 4
check(f"收合時遮罩寬度 <= {limit}px", mask_w <= limit, True)
print(f"       實際 {mask_w}px（藥丸 {isl.PILL_MIN[0]}px + 陰影，視窗 {isl.WIN_W}px）")

print("\n14. 頂端探頭：不依賴系統匣的入口")
scr = QApplication.primaryScreen().geometry()
CURSOR = [scr.center().x(), 0]
isl.cursor_pos = lambda: (CURSOR[0], CURSOR[1])

w.drinks = 2
w._peeking = False
w._peek_locked = False
w._enter(isl.NORMAL)
settle_springs()

CURSOR[:] = [scr.center().x() + 800, 500]      # 滑鼠在別處
w._peek_tick()
check("滑鼠在別處不探頭", w._peeking, False)

CURSOR[:] = [scr.center().x(), scr.top() + 2]  # 移到頂端中央
w._peek_tick()
check("進熱區就探頭", w._peeking, True)
check("reveal 目標", w.sp_reveal.target, 1.0)
check("探頭是收合尺寸", w.sp_expand.target, 0.0)

CURSOR[:] = [scr.center().x(), 600]            # 移開
w._peek_tick()
check("離開就收回去", w._peeking, False)
check("reveal 目標", w.sp_reveal.target, 0.0)

print("\n15. 提醒中不受探頭邏輯干擾")
w._enter(isl.THIRSTY)
settle_springs()
CURSOR[:] = [scr.center().x(), 600]
w._peek_tick()
check("狀態不變", w.state, isl.THIRSTY)
check("不會被收掉", w.sp_reveal.target, 1.0)

print("\n16. 喝完後滑鼠還停在島上，不該立刻又探頭")
CURSOR[:] = [scr.center().x(), scr.top() + 2]
w.drink()
w._settle()                                    # 閃爍結束
check("已上鎖", w._peek_locked, True)
w._peek_tick()
check("鎖住時不探頭", w._peeking, False)
CURSOR[:] = [scr.center().x(), 600]            # 離開熱區
w._peek_tick()
check("離開後解鎖", w._peek_locked, False)
CURSOR[:] = [scr.center().x(), scr.top() + 2]  # 再回來
w._peek_tick()
check("解鎖後可再探頭", w._peeking, True)

print("\n17. 重啟後計時要接得回來（不然倒數會莫名變多）")
w.drinks = 2
w.active_s = 1800.0
w.interval_s = 3600.0
w.paused_until = None
w._persist()

w2 = isl.Island(cfg)
w2.tick_timer.stop(); w2.frame.stop(); w2.hold_timer.stop(); w2.peek_timer.stop()
check("次數接回", w2.drinks, 2)
check("累積時間接回", w2.active_s, 1800.0)
check("間隔沒被重擲", w2.interval_s, 3600.0)
# 深夜與否要由測試決定，不能交給真實時鐘：_status_sub() 在深夜會多一段
# 「深夜放慢」，這幾條若在 23:00-08:00 之間跑就會拿到另一個字串而莫名變紅。
w2._is_late = lambda hour=None: False
w2.streak = 0        # 沒有連續時，開頭仍顯示今天次數
check("倒數一致", w2._status_sub(),
      f"今天 2/{cfg['daily_target_drinks']} 次 · 下次約 30 分後")
w2.streak = 5        # 有連續時，開頭換成連續天數（進度點已表達今天次數）
check("有連續時顯示連續", w2._status_sub(), "連續 5 天 · 下次約 30 分後")
check("提醒中的小標", w2._reminding_sub(),
      f"連續 5 天 · 今天 2/{cfg['daily_target_drinks']} 次")
# 深夜必須看得見。抖動有 ±15%，所以「這次怎麼比較久」在畫面上跟深夜模式
# 長得一模一樣——不標示的話，這個全自動、推導可能算錯的機制壞掉時無從歸因。
# 標示的做法是換掉「下次」而不是插入一段：插入就得多一個分隔點，而最長情況
# 只剩 34px 餘裕，插什麼都會被截掉。
w2._is_late = lambda hour=None: True
check("深夜時副標要看得出來", w2._status_sub(), "連續 5 天 · 夜間約 30 分後")
w2._is_late = lambda hour=None: False
w2.streak = 0

print("\n17b. 進度點變多後，文字不能被省略號截掉")
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPixmap  # noqa: E402

w2.sp_expand.value = w2.sp_expand.target = 1.0
w2.sp_expand.velocity = 0.0
w2.sp_reveal.value = w2.sp_reveal.target = 1.0
# sp_content 也要推到底：pill_rect() 會用它把寬度收回「內容剛好放得下」，
# 只設 sp_expand 量到的是收合寬度，文字當然放不下（實測可用寬度 -49px）。
# 這是 sp_content 從 sp_expand 拆出來之後，測試沒跟著更新的殘留。
w2.sp_content.value = w2.sp_content.target = 1.0
w2.sp_content.velocity = 0.0
rect = w2.pill_rect()

pm = QPixmap(isl.WIN_W, isl.WIN_H)
p = QPainter(pm)
# 版面照抄 paintEvent 的算法，不在這裡另外寫一份——臉與進度點共用同一份
# _layout()，測試自己算等於埋下第二份會漂開的公式。
lay = w2._layout(rect, isl.clamp(w2.sp_content.value, 0.0, 1.0))
pips_left = w2._draw_pips(p, rect, lay)   # 回傳進度點的左緣
# 文字起點要由實際畫出來的角色決定，不能在這裡另外抄一份公式——
# 換角色造型（幾何臉 <-> 像素杯）寬度就會變，兩份公式一定會漂開。
face = w2._draw_face(p, rect, QColor(isl.VISUAL[w2.state][0]), lay)
p.end()

text_x = face.right() + rect.height() * 0.22
avail = pips_left - 16 - text_x

w2.streak = 128          # 三位數的連續天數是最長情況，要一起驗
w2.interval_s = 100 * 60
w2.active_s = 0.0
# 真正的最長情況是深夜版的倒數，白天版量不到它。第一版加深夜標示時
# 就是只驗了白天版才漏掉：當時的寫法實測 264px、可用 262px，剛好被截 2px。
w2._is_late = lambda hour=None: False
_sub_day = w2._status_sub()
w2._is_late = lambda hour=None: True
_sub_late = w2._status_sub()
w2._is_late = lambda hour=None: False
for label, text, font in (
    ("倒數（連續破百）", _sub_day, w2._f_sub),
    ("倒數（連續破百·深夜）", _sub_late, w2._f_sub),
    ("提醒中（連續破百）", w2._reminding_sub(), w2._f_sub),
    ("打招呼副標", "游標移至螢幕上緣中央可呼叫", w2._f_sub),
    ("最長標題", "今天達標了", w2._f_title),
):
    need = QFontMetrics(font).horizontalAdvance(text)
    fits = need <= avail
    print(("  ok  " if fits else "  FAIL") +
          f"  {label}：需要 {need}px / 可用 {avail:.0f}px　「{text}」")
    if not fits:
        fails.append(f"文字被截：{label}")

print("\n17c. 重啟不能重發提醒（多出來的事件會污染作息推導）")
# 狀態沒跨重啟保存時，重開一律從 NORMAL 起算，而 active_s 已經超過間隔，
# tick() 就會立刻再發一次提醒。實測那些多餘的 remind 事件會把活動紀錄的
# 安靜段填掉，讓 settings.infer_wake_hour() 直接回 None。
w2.state = isl.THIRSTY
w2.active_s = w2.interval_s + 60
w2.drinks = 2
w2._persist()
check("狀態有落檔", isl.load_state().get("state"), isl.THIRSTY)

_before = sum(1 for _ in open(isl.EVENTS_PATH, encoding="utf-8"))
w5 = isl.Island(cfg)
w5.tick_timer.stop(); w5.frame.stop(); w5.hold_timer.stop(); w5.peek_timer.stop()
check("重啟後接回原本的狀態", w5.state, isl.THIRSTY)
w5.tick()
_after = sum(1 for _ in open(isl.EVENTS_PATH, encoding="utf-8"))
check("重啟後 tick 不會再發一次提醒", _after, _before)

print("\n18. 距上次存檔超過 12 小時就重新開始，不把昨天的累積算進來")
stale = isl.load_state()
stale["saved_ts"] = (datetime.now() - timedelta(hours=13)).isoformat(timespec="seconds")
isl.save_state(stale)
w3 = isl.Island(cfg)
w3.tick_timer.stop(); w3.frame.stop(); w3.hold_timer.stop(); w3.peek_timer.stop()
check("累積時間歸零", w3.active_s, 0.0)
check("間隔重新擲過", w3.interval_s != 3600.0, True)

print("\n19. 暫停狀態也要跨重啟保留")
w3.paused_until = datetime.now() + timedelta(hours=2)
w3._persist()
w4 = isl.Island(cfg)
w4.tick_timer.stop(); w4.frame.stop(); w4.hold_timer.stop(); w4.peek_timer.stop()
check("暫停接回", w4.paused_until is not None, True)

print("\n20. 滑鼠掃過藥丸：過期的延遲不能把字又叫回來")
# 症狀是藥丸縮到停留尺寸、字卻留在上面被擠成「現在…」，而且不會自己恢復。
# 需要真的事件迴圈，延遲計時器才會開火。
from PySide6.QtCore import QEventLoop  # noqa: E402
from PySide6.QtCore import QTimer as _QTimer  # noqa: E402


def wait_ms(ms):
    loop = QEventLoop()
    _QTimer.singleShot(ms, loop.quit)
    loop.exec()


w5 = isl.Island(cfg)
w5.tick_timer.stop(); w5.frame.stop(); w5.peek_timer.stop()
w5._enter(isl.THIRSTY)
w5.hold_timer.stop()               # 只驗滑鼠這條路徑，停留計時不參與
wait_ms(200)                       # 讓 _enter 的 90ms 延遲先跑完
w5.enterEvent(None)                # 進入 -> 排定 60ms 後把字叫回來
wait_ms(20)                        # 還沒到 60ms
w5.leaveEvent(None)                # 就離開 -> _settle()：字先走、藥丸縮到 0.35
check("leave 當下字要走", w5.sp_content.target, 0.0)
wait_ms(200)                       # 過期的那一發會在這區間開火
check("過期延遲不得覆蓋", w5.sp_content.target, 0.0)
check("藥丸停在口渴的停留尺寸", round(w5.sp_expand.target, 2), 0.35)

print("\n20b. 收合中途下的延遲同樣要能被取消")
w5._target_content(1.0, delay_ms=90)
w5._target_content(0.0)            # 立刻改主意
wait_ms(200)
check("後下的目標說了算", w5.sp_content.target, 0.0)

print("\n21. 角色尺寸在動畫中不能來回跳（會看成「變小又變大」）")
# 第一版讓格距跟著藥丸高度走，展開彈簧阻尼 0.70 會過衝震盪，
# 而 100 × 0.60 ÷ 15 剛好整除 —— 高度掉 0.1px 格距就掉一級，於是杯子反覆縮放。
# 判準：一次轉場裡尺寸最多只變一次，且不得回頭。
pm6 = QPixmap(isl.WIN_W, isl.WIN_H)
w6 = isl.Island(cfg)
for _t in (w6.tick_timer, w6.peek_timer, w6.frame, w6.hold_timer):
    _t.stop()


def size_runs(start, target, state):
    w6.state = state
    w6.sp_expand.value, w6.sp_expand.velocity = start, 0.0
    w6._target_expand(target)
    seen = []
    for _ in range(120):                      # 2 秒，足夠收斂
        w6.sp_expand.step(1 / 60)
        _p = QPainter(pm6)
        _rect = w6.pill_rect()
        box = w6._draw_face(_p, _rect, QColor(isl.VISUAL[state][0]),
                            w6._layout(_rect, isl.clamp(w6.sp_content.value, 0.0, 1.0)))
        _p.end()
        size = (int(box.width()), int(box.height()))
        if not seen or seen[-1] != size:
            seen.append(size)
    return seen


def monotonic(runs):
    """尺寸序列只能一路變大或一路變小，不能中途回頭。

    原本這裡驗的是「變化次數 <= 2」，那是「不能來回跳」的代理指標，
    而且是在杯子只有一種原生尺寸的時候寫的。現在 pixelface.cup_cell_for()
    有三種渲染（只畫臉 / 小杯 / 大杯），一次完整展開本來就會經過三個尺寸——
    那是單調遞增，不是來回跳，代理指標卻把它判成失敗。
    直接驗真正在意的性質：方向不能反轉。
    """
    ws = [s[0] for s in runs]
    return ws == sorted(ws) or ws == sorted(ws, reverse=True)


for _label, _a, _b, _st in (("展開 0->1", 0.0, 1.0, isl.NORMAL),
                            ("收到停留 1->0.35", 1.0, 0.35, isl.THIRSTY),
                            ("隱藏 1->0", 1.0, 0.0, isl.NORMAL)):
    _runs = size_runs(_a, _b, _st)
    check(f"{_label} 尺寸不回頭", monotonic(_runs), True)
    # 三種渲染是設計上的上限（只畫臉 / 小杯 / 大杯）。超過就是有人加了新尺寸，
    # 動畫中的階梯會變密，要回來重新評估。
    check(f"{_label} 尺寸種類 <= 3", len(_runs) <= 3, True)
    if not monotonic(_runs) or len(_runs) > 3:
        print(f"       實際變化序列：{_runs}")

print("\n22. 提醒中把目標調低到已達成，島要走掉，不能卡在畫面上")
# tick() 的達標守門是 `return`，它只擋「不再發新的提醒」，擋不掉已經在畫面上
# 的那一個。所以提醒中把每日目標調低（或改體重讓推導值下降），島就卡在
# 「拜託」配「今天 7/7 次」，一路留到隔天換日。使用者截圖回報的就是這個。
w22 = isl.Island(dict(cfg, daily_target_drinks=8))
for _t in (w22.tick_timer, w22.frame, w22.hold_timer, w22.peek_timer):
    _t.stop()
# 島啟動時會從 state.json 接回上一次的狀態，而第 19 節在那裡留下了「暫停中」。
# 不清掉的話 tick() 會在暫停檢查就 return，這一節其實什麼都沒驗到。
w22.paused_until = None
w22.drinks = 7
w22._enter(isl.WEAK)
check("起點：提醒中且還沒達標", (w22.state, w22.sp_reveal.target), (isl.WEAK, 1.0))
w22.apply_config(dict(cfg, daily_target_drinks=7))
check("目標調低到已達成 -> 立刻收掉", w22.state, isl.NORMAL)
check("而且是滑走，不是留在原地", w22.sp_reveal.target, 0.0)
for _ in range(200):
    w22.tick()
check("之後也不會再冒出來", (w22.state, w22.sp_reveal.target), (isl.NORMAL, 0.0))

# 反向也要對：目標調高之後又還沒達標，就該恢復提醒。
# 只修「調低」很容易寫成無條件收掉，那會讓調高目標的人再也收不到提醒。
w22b = isl.Island(dict(cfg, daily_target_drinks=7))
for _t in (w22b.tick_timer, w22b.frame, w22b.hold_timer, w22b.peek_timer):
    _t.stop()
w22b.paused_until = None
w22b.drinks = 7
w22b.apply_config(dict(cfg, daily_target_drinks=9))
w22b.active_s = w22b.interval_s + 1
w22b.tick()
check("目標調高之後還能再提醒", w22b.state, isl.THIRSTY)

print("\n22b. 已達標卻卡在提醒中的狀態，重啟後也要收掉")
# 這一節才是真正咬到使用者的那條路。第一版只補了 apply_config（在設定裡
# 把目標調低），但狀態會跨重啟保存——島一旦卡住，每次開機都把那個狀態原封接回來，
# 重開程式等於把同一個 bug 重建一次。使用者實測「沒有改善」，state.json 裡就是
# drinks=7 / state=WEAK / 目標 7。
w22c = isl.Island(dict(cfg, daily_target_drinks=7))
for _t in (w22c.tick_timer, w22c.frame, w22c.hold_timer, w22c.peek_timer):
    _t.stop()
w22c.paused_until = None
w22c.drinks = 7
w22c.state = isl.WEAK          # 直接偽造「上次存檔時卡住了」
w22c._persist()
check("存檔裡確實是卡住的狀態",
      (isl.load_state()["state"], isl.load_state()["drinks"]), ("WEAK", 7))

w22d = isl.Island(dict(cfg, daily_target_drinks=7))
for _t in (w22d.tick_timer, w22d.frame, w22d.hold_timer, w22d.peek_timer):
    _t.stop()
w22d.paused_until = None
check("重啟後確實接回了那個狀態", (w22d.state, w22d.drinks), (isl.WEAK, 7))
w22d.tick()
check("第一個 tick 就收掉", w22d.state, isl.NORMAL)
check("而且是滑走", w22d.sp_reveal.target, 0.0)
# 存檔也要更新，否則下次啟動又接回同一個狀態，等於沒修
check("存檔跟著更新，不會再接回來", isl.load_state()["state"], "NORMAL")

print("\n23. 引導的練習點擊不能留下任何痕跡")
# 引導最後一頁寫著「這次不會算進今天的次數」。那是對使用者的承諾，要能驗。
# drink() 裡每一行都有副作用（次數、累積時間、重擲間隔、寫 events、存檔），
# 練習那條路必須在最前面就 return。
w23 = isl.Island(dict(cfg))
for _t in (w23.tick_timer, w23.frame, w23.hold_timer, w23.peek_timer):
    _t.stop()
w23.paused_until = None
w23.drinks = 2
w23.active_s = 900.0
before = (w23.drinks, w23.active_s, w23.interval_s,
          os.path.getsize(isl.EVENTS_PATH) if os.path.exists(isl.EVENTS_PATH) else 0,
          isl.load_state())

called = []
w23.practice(lambda: called.append(1))
check("練習模式：島出來了", w23.sp_reveal.target, 1.0)
check("而且是提醒中的樣子", w23.state, isl.THIRSTY)

w23.drink()
after = (w23.drinks, w23.active_s, w23.interval_s,
         os.path.getsize(isl.EVENTS_PATH) if os.path.exists(isl.EVENTS_PATH) else 0,
         isl.load_state())
check("次數沒變", after[0], before[0])
check("累積的在電腦前時間沒被歸零", after[1], before[1])
check("這一輪的間隔沒被重擲", after[2], before[2])
check("沒有寫進事件紀錄", after[3], before[3])
check("沒有存檔", after[4], before[4])
check("有回呼給引導", called, [1])
check("點完是滿足的樣子", w23.state, isl.SATISFIED)

# 練習只有一次。旗標沒清乾淨的話，之後每一次真的喝水都不會被記——
# 那是這個 bug 最壞的形式：使用者以為有記，資料卻是空的。
w23.drink()
check("練習之後恢復正常計數", w23.drinks, before[0] + 1)

print("\n24. 右鍵選單開著的時候，島不能收回去")
# 選單畫在島的下方，所以「把滑鼠移過去點」這個動作本身就會同時離開熱區、
# 離開藥丸、觸發 leaveEvent。三條收合路徑各自都會把島收掉，而使用者的手
# 還在半路上。島一收，選單就沒有依附的東西，看起來像整組消失，而離選單
# 越遠的項目越難點到——「設定」排第四，所以最常被回報成沒有反應。
from PySide6.QtCore import QPoint  # noqa: E402

_saved_cursor = isl.cursor_pos
isl.cursor_pos = lambda: (5, 900)          # 游標遠離熱區，模擬滑向選單


def _peeking_island():
    w = isl.Island(dict(cfg))
    w.tick_timer.stop()
    w._enter(isl.NORMAL)                   # 平常隱藏，探頭邏輯才會作用
    w._peeking = True
    w._target_reveal(1.0)
    return w


w24 = _peeking_island()
w24._peek_tick()
check("沒有選單時本來就會收（確認這條測試有效）", w24.sp_reveal.target, 0.0)

w24 = _peeking_island()
w24._popup_menu(QPoint(600, 300))
check("選單認得出自己開著", w24._menu_open(), True)
w24._peek_tick()
check("探頭輪詢不收", w24.sp_reveal.target, 1.0)
w24._settle()
check("停留結束不收", w24.sp_reveal.target, 1.0)
w24.leaveEvent(None)
check("滑鼠移出島也不收", w24.sp_reveal.target, 1.0)

# 擋下來的收合要補做，否則島會一直掛在畫面上
w24._menu_ref.close()
w24._menu_dismissed()
check("選單關掉後補收回去", w24.sp_reveal.target, 0.0)
isl.cursor_pos = _saved_cursor

print("\n25. 探頭熱區的寬度不能被顯示縮放放大")
# 上下限講的是「手能不能瞄準」與「會不會誤觸」，那是實體尺寸。
# Qt 給的螢幕寬是邏輯像素，直接拿去夾的話，防呆自己會變成災情：
# 1366 的小筆電在 200% 縮放下，熱區會被 MIN 撐到佔螢幕寬 41%——
# 上緣中段四成都會叫出島。修正前後的數字見 DESIGN.md。
_bad = []
for _phys in (1366, 1920, 2560, 3440, 3840):
    _ratios = []
    for _sc in (1.0, 1.25, 1.5, 2.0):
        _lw = int(_phys / _sc)
        _ratios.append(isl.peek_half_w(_lw, _sc) * 2 / _lw * 100)
    # 同一台實體螢幕，不管使用者把縮放調到多少，熱區佔的比例應該一樣
    if max(_ratios) - min(_ratios) > 0.5:
        _bad.append((_phys, [round(r, 1) for r in _ratios]))
check("同一台螢幕在四種縮放下熱區比例一致", _bad, [])
check("小筆電 @200% 不會被撐到誤觸區",
      round(isl.peek_half_w(683, 2.0) * 2 / 683 * 100, 1) < 25.0, True)
check("dpr 給 0 或 None 也不能除爆", isl.peek_half_w(1920, 0), isl.peek_half_w(1920, 1.0))

print("\n99. 整支測試不能碰到使用者真實的資料檔")
# Qt 會吞掉 slot 裡拋出的例外——只把 traceback 印到 stderr 然後繼續跑。
# 所以光靠 settings 的防線拋例外還不夠：自動化跑完照樣顯示「全部通過」，
# 而它其實已經闖進真實資料。這一條把印出來的 traceback 變成可斷言的事實。
check("防線沒有攔截到任何寫入", isl.settings.real_write_violations(), [])

print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 項失敗：{fails}"))
sys.exit(1 if fails else 0)

# -*- coding: utf-8 -*-
"""驗證正式版動態島：計時、閒置暫停、升級、達標、換日、暫停、統計、顯示與隱藏。"""
import io
import json
import os
import shutil
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import island as isl  # noqa: E402
import settings as ap  # noqa: E402

TEST_DIR = os.path.join(SCRATCH, "wp_island")
shutil.rmtree(TEST_DIR, ignore_errors=True)
isl.DATA_DIR = TEST_DIR
isl.STATE_PATH = os.path.join(TEST_DIR, "state.json")
isl.EVENTS_PATH = os.path.join(TEST_DIR, "events.jsonl")
# settings 那一側也要指進沙箱。drink() 第一次達標時會 save_config() 把
# records_hinted 寫回去，而它走的是 settings.CONFIG_PATH，不是上面那三個。
# 沒有這兩行，跑一次測試就會動到使用者真實的設定檔（第 99 節會抓到）。
ap.DATA_DIR = TEST_DIR
ap.CONFIG_PATH = os.path.join(TEST_DIR, "config.json")

IDLE = [0.0]
isl.idle_seconds = lambda: IDLE[0]

from datetime import datetime, timedelta  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
cfg = dict(isl.DEFAULT_CONFIG)
cfg["tick_seconds"] = 60          # 一 tick 當一分鐘，快轉用
# 「右鍵可以看紀錄」一輩子只出現一次，而它會蓋掉達標時的「連續 N 天」。
# 底下絕大多數的節驗的是常態行為，所以預設當成「已經提示過」。
# 第一次達標的那條路由第 33 節自己把旗標關掉來驗。
cfg["records_hinted"] = True
w = isl.Island(cfg)
w.tick_timer.stop()
w.frame.stop()
w.hold_timer.stop()
# 定期落檔也要停。它每 PERSIST_SECONDS（60）秒把 state.json 覆寫一次，留著跑
# 的話會在測試中途蓋掉第 17～19 節刻意擺好的存檔，那幾節就會時好時壞——
# 而那種失敗最難查。
w.beat_timer.stop()

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


def sip(widget, times=1):
    """模擬補水，代表「兩次之間有時間經過」。

    drink() 有防連點：satisfied_flash_seconds 之內的第二下會被丟掉
    （使用者回報「不小心一次點了兩次」）。而真實世界兩次補水之間至少隔著
    一個提醒間隔，測試在微秒之間連呼叫等於在測那個被刻意擋掉的行為，
    所以要把時間戳往回撥。

    直接呼叫 widget.drink() 的測試會被防連點擋住而失敗——那不是壞掉，
    是它在模擬一件現實中做不到的事。
    """
    for _ in range(times):
        widget._last_drink_at = -1e9
        widget.drink()


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
sip(w)
check("狀態", w.state, isl.SATISFIED)
check("次數", w.drinks, 1)
check("active_s 歸零", w.active_s, 0.0)
check("訊息", w.message, f"喝了，還剩 {cfg['daily_target_drinks'] - 1} 次")
w._settle()                      # 模擬閃爍時間結束
check("狀態", w.state, isl.NORMAL)
check("reveal 目標（消失）", w.sp_reveal.target, 0.0)

print("\n9. 補滿 6 次 -> 達標訊息，之後整天不再出現")
sip(w, cfg["daily_target_drinks"] - 1)
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
# 這個替身裝上去就不拆了（後面的探頭測試都靠它），所以真本尊要先留一份——
# 第 25b 節要驗的是本尊的座標系，驗替身沒有意義。
REAL_CURSOR_POS = isl.cursor_pos
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
sip(w)
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
# 次數搬到主字之後，這一行不再重複它——「還剩 3 次」配「今天 2/7 次」是
# 同一件事講兩遍，而連續天數才是這條線上最該被看到的東西。
check("提醒中的小標只講連續", w2._reminding_sub(), "連續 5 天")
w2.streak = 0
check("還沒有連續可講的第一天，次數仍然放這裡", w2._reminding_sub(),
      f"今天補水 2/{cfg['daily_target_drinks']} 次")
w2.streak = 5
# 深夜不標示。先前寫「夜間約 N 分後」，但深夜的範圍一路延續到起床時間，
# 於是起床設 9 點的人早上 8:40 會看到「夜間」——那一刻事實上沒錯（間隔確實
# 還是放慢的），但讀起來是錯的，而讀起來是錯的標籤比沒有標籤糟。
w2._is_late = lambda hour=None: True
check("深夜也是同一句，不特別標示", w2._status_sub(), "連續 5 天 · 下次約 30 分後")
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


def _avail_for(title, sub):
    """把這段文字真的放進島裡，量它剩下多少可用寬度。

    **可用寬度不能在迴圈外面量一次就好。** 藥丸的寬度現在跟著內容走
    （見 pill_rect），所以每一句話對應到的是一個不同寬度的藥丸——
    在外面量一次等於拿「上一句話的藥丸」去驗這一句，量錯了還會是綠燈。
    這一節先前就是那樣寫的，改成內容驅動寬度之後它會變成假通過。
    """
    w2._set_text(title, sub)
    # 寬度是彈簧推過去的（見 _set_text）。這一節驗的是版面，不是動畫過程，
    # 所以直接把彈簧推到定位——不推的話量到的是上一句話的寬度。
    w2.sp_text_w.value, w2.sp_text_w.velocity = w2.sp_text_w.target, 0.0
    r = w2.pill_rect()
    pm_ = QPixmap(isl.WIN_W, isl.WIN_H)
    p_ = QPainter(pm_)
    lay_ = w2._layout(r, isl.clamp(w2.sp_content.value, 0.0, 1.0))
    pips_l = w2._draw_pips(p_, r, lay_)
    f_ = w2._draw_face(p_, r, QColor(isl.VISUAL[w2.state][0]), lay_)
    p_.end()
    return pips_l - 16 - (f_.right() + r.height() * 0.22), r.width()


_msg0, _sub0 = w2.message, w2.sub_message
# 文字沒走 _set_text 的話寬度不會更新，藥丸會拿上一句的寬度裝這一句。
# 這一條守著那個入口：繞過去就會被抓到。
w2._set_text("水呢", "口渴的時候身體已經流失百分之二的水分")
check("換文字會同時改寬度目標", w2.sp_text_w.target > 0, True)
for label, text, font in (
    ("倒數（連續破百）", _sub_day, w2._f_sub),
    ("倒數（連續破百·深夜）", _sub_late, w2._f_sub),
    ("提醒中（連續破百）", w2._reminding_sub(), w2._f_sub),
    ("打招呼副標", "游標移至螢幕上緣中央可呼叫", w2._f_sub),
    # 第一次達標那句提示也走小標，而且它是一次性的：被截掉就永遠沒有第二次。
    ("第一次達標的提示", "右鍵可以看紀錄", w2._f_sub),
    ("最長標題", "今天達標了", w2._f_title),
    # 提示句會比現有文案長，而藥丸現在會自己長。上限由螢幕決定，
    # 超過就該被夾住而不是把島撐成橫幅——夾住之後這條會 FAIL，那是對的。
    ("二十字的提示句", "口渴的時候身體已經流失百分之二的水分", w2._f_sub),
):
    is_title = font is w2._f_title
    avail, pill_w = _avail_for(text if is_title else "水呢",
                               text if not is_title else "今天 2/7 次")
    need = QFontMetrics(font).horizontalAdvance(text)
    fits = need <= avail
    print(("  ok  " if fits else "  FAIL") +
          f"  {label}：需要 {need}px / 可用 {avail:.0f}px"
          f" / 藥丸 {pill_w:.0f}px　「{text}」")
    if not fits:
        fails.append(f"文字被截：{label}")
w2.message, w2.sub_message = _msg0, _sub0

# 藥丸不能比螢幕還寬，也不能比內容還寬。前者是版面災難，後者是先前的樣子
# （兩個字的「倒了」撐出一個 462px 的殼，中間空一大片）。
_short_avail, _short_w = _avail_for("倒了", "今天 2/7 次")
_long_avail, _long_w = _avail_for("水呢", "口渴的時候身體已經流失百分之二的水分")
check("短句子的島比長句子窄", _short_w < _long_w, True)
check("而且沒有超過螢幕能容許的上限",
      _long_w <= w2._max_pill_w() + 0.5, True)
check("視窗畫布容得下最寬的藥丸（不然圓角會被切掉）",
      isl.PILL_MAX[0] + (isl.SQUASH_MAX + isl.PILL_SHADOW) * 2 <= isl.WIN_W, True)
w2.message, w2.sub_message = _msg0, _sub0

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

sip(w23)
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
sip(w23)
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

print("\n25. 探頭熱區在任何顯示縮放下都是同一個實體大小")
# **一定要量實體像素。** 上下限講的是「手能不能瞄準」「會不會誤觸」，那是眼睛
# 與滑鼠的事；使用者的手也是在實體像素裡移動的。
#
# 第一版的這條測試量的是「佔邏輯寬的比例」，結果測試綠燈但東西是壞的——
# 那個指標不是使用者感受到的那個。量錯座標系的測試比沒有測試更糟，
# 它會發出「已經驗過了」的訊號。
_bad = []
for _phys in (1366, 1920, 2560, 3440, 3840):
    _widths = []
    for _sc in (1.0, 1.25, 1.5, 2.0):
        _lw = int(_phys / _sc)
        # peek_half_w 回的是邏輯像素（跟 geometry() 同一個座標系），
        # 乘回 dpr 才是使用者的手要跨過的實際距離。
        _widths.append(isl.peek_half_w(_lw, _sc) * 2 * _sc)
    if max(_widths) - min(_widths) > 4:          # 4px 是整數取整的餘裕
        _bad.append((_phys, [round(w) for w in _widths]))
check("同一台螢幕在四種縮放下實體熱區寬度一致", _bad, [])
check("上下限是實體像素：1366 @200% 仍是 280 實體像素",
      round(isl.peek_half_w(683, 2.0) * 2 * 2.0), 280)
check("dpr 給 0 或 None 也不能除爆", isl.peek_half_w(1920, 0), isl.peek_half_w(1920, 1.0))

print("\n25b. 游標座標必須跟 geometry() 同一個座標系")
# 這一條是上一條的前提。熱區的比較式是 abs(游標x - geometry().center().x())，
# 兩邊的座標系一旦不同，夾多寬都沒有意義。
# Qt6 預設把程序設成 per-monitor DPI aware，Win32 的 GetCursorPos 回實體像素，
# 而 QScreen.geometry() 回邏輯像素——100% 縮放時兩者相同，所以這個 bug
# 可以躺很久不被發現。
from PySide6.QtGui import QCursor as _QCursor  # noqa: E402
_qt = _QCursor.pos()
check("cursor_pos() 回的是 Qt 的邏輯座標", REAL_CURSOR_POS(), (_qt.x(), _qt.y()))
# 反過來也要擋住：如果哪天有人改回 Win32 的 GetCursorPos，這一條會在
# 100% 縮放下照樣通過（那時兩者相同），所以另外比一次實體座標。
import ctypes as _ct  # noqa: E402
from ctypes import wintypes as _wt  # noqa: E402
_pt = _wt.POINT()
_ct.WinDLL("user32").GetCursorPos(_ct.byref(_pt))
_dpr = QApplication.primaryScreen().devicePixelRatio()  # noqa: F811
check("而且在縮放不是 1 時，跟 Win32 的實體座標確實不同",
      (REAL_CURSOR_POS()[0] == _pt.x) if _dpr == 1.0 else (REAL_CURSOR_POS()[0] != _pt.x),
      True)

print("\n26. 手滑點兩下只能記一次")
# 使用者回報：「可以重置計算嗎，不小心一次點了兩次之類的」。
# 他要的是撤銷，該修的是別讓它記到兩次。
w26 = isl.Island(dict(cfg))
w26.tick_timer.stop(); w26.frame.stop(); w26.hold_timer.stop(); w26.peek_timer.stop()
w26.drinks = 0
w26.drink()
_after_first = w26.drinks
w26.drink()                                   # 立刻再一下，模擬手滑
check("第一下記了", _after_first, 1)
check("緊接著的第二下不算", w26.drinks, 1)

# 而且不能只是「這一下不算」——它不該留下任何痕跡
_events = sum(1 for _ in open(isl.EVENTS_PATH, encoding="utf-8")) \
    if os.path.exists(isl.EVENTS_PATH) else 0
w26.drink()
check("被擋下的那一下沒有寫進事件紀錄",
      sum(1 for _ in open(isl.EVENTS_PATH, encoding="utf-8")), _events)

# 隔了夠久就要記得下來。這一條是防呆的另一半：擋太多比擋太少嚴重，
# 因為「記不進去」是無聲的，使用者以為有記，資料卻是空的。
w26._last_drink_at -= cfg["satisfied_flash_seconds"] + 1
w26.drink()
check("過了確認訊息的時間就正常記", w26.drinks, 2)

# 系統匣的左鍵不再記水。一般人對系統匣圖示的預期是「點了會打開什麼」，
# 而先前點下去什麼都沒開、背後卻記了一次——第一次用的人好奇點一下，
# 資料就髒了，而且他不會知道（島那時是隱藏的，沒有任何回饋）。
_opened = []
w26.show_stats = lambda: _opened.append(1)
_before26 = w26.drinks
w26._tray_clicked(isl.QSystemTrayIcon.Trigger)
check("系統匣左鍵不再記水", w26.drinks, _before26)
check("而是打開喝水紀錄", len(_opened), 1)

print("\n27. 提示音只在升級的那一刻響")
# 聲音是升級階梯的最後一階（換色 -> 變大 -> 不消失 -> 出聲）。
# 三件事要守住：提醒本身不出聲、升級才出聲、而且啟動時接回狀態不能出聲。
_played = []
_real_play = isl.sound.play
isl.sound.play = lambda name: _played.append(name) or True


def esc(widget, n):
    for _ in range(n):
        widget.tick()


def fresh(**over):
    """乾淨的一顆島。

    刻意把接回來的狀態清掉：前面的段落存過 state.json，不清的話這裡量到的是
    別人留下的次數與累積時間——而那個值每次跑都不一樣，測試會時好時壞。
    """
    c = dict(cfg)
    c.update(over)
    x = isl.Island(c)
    x.tick_timer.stop(); x.frame.stop(); x.hold_timer.stop(); x.peek_timer.stop()
    x.beat_timer.stop()          # 理由同檔案開頭：定期落檔會蓋掉測試擺好的存檔
    x.drinks = 0
    x.active_s = 0.0
    x.state = isl.NORMAL
    x._undo = None
    return x


w27 = fresh()
esc(w27, int(w27.interval_s / 60) + 1)
check("狀態", w27.state, isl.THIRSTY)
# 這一條是整個設計的前提。每次提醒都響的話，一天七聲同樣的聲音，
# 兩天就會被自動過濾掉——而那個過濾會連帶讓人對整個工具脫敏。
check("第一次提醒不出聲", _played, [])

esc(w27, cfg["escalate_weak_min"] + 1)
check("狀態", w27.state, isl.WEAK)
check("升級到虛弱才響第一聲", _played, ["weak"])

esc(w27, cfg["escalate_collapsed_min"] - cfg["escalate_weak_min"] + 1)
check("狀態", w27.state, isl.COLLAPSED)
check("倒地是另一個聲音", _played, ["weak", "collapsed"])

# 關掉音效關掉的是「出聲」，不是升級。島照樣走完整條階梯——
# 這是它跟「關閉提醒總開關」的差別，見 settings.py 開頭。
_played.clear()
w27b = fresh(sound_enabled=False)
esc(w27b, int(w27b.interval_s / 60) + 1 + cfg["escalate_collapsed_min"] + 1)
check("關掉之後完全不出聲", _played, [])
check("但升級照樣發生", w27b.state, isl.COLLAPSED)

# 啟動時接回上次的狀態走的是 _enter()，那條路不能響：收工時島正好停在虛弱，
# 隔天一開機就會被沒頭沒尾地叫一聲。所以 _chime() 刻意不寫在 _enter() 裡。
_played.clear()
w27.state = isl.THIRSTY
w27._enter(isl.WEAK)
check("直接進入狀態（啟動接回）不出聲", _played, [])
w27._enter(isl.COLLAPSED)
check("倒地也一樣", _played, [])

isl.sound.play = _real_play

print("\n28. 退回上一次記錄")
# 防連點只擋得住「手滑點兩下」。點錯了、或點完才發現自己其實沒喝，
# 那些擋不到，所以要有一條退路。
import json  # noqa: E402

import dashboard as dash  # noqa: E402

# 自己一份紀錄檔。共用的那個裡面有前面段落寫進去的補水，
# 混在一起就分不出「統計扣掉了沒有」。
_ev_save = isl.EVENTS_PATH
isl.EVENTS_PATH = os.path.join(TEST_DIR, "undo_events.jsonl")

w28 = fresh()
esc(w28, int(w28.interval_s / 60) + 1 + cfg["escalate_weak_min"] + 1)
check("先讓它升級到虛弱", w28.state, isl.WEAK)
_before = (w28.active_s, w28.interval_s)

sip(w28)
check("記了一次", w28.drinks, 1)
check("倒數歸零", w28.active_s, 0.0)

w28.undo_drink()
check("次數退回去了", w28.drinks, 0)
# 這三條是這個功能的重點：退回不能變成另一種「關掉提醒」。
# 只改次數不動計時的話，點一下＋退回一次就是一顆隱藏的關閉鍵。
check("累積的時間也還原", w28.active_s, _before[0])
check("那一輪的間隔也還原", w28.interval_s, _before[1])
check("島回到按下去之前那一級", w28.state, isl.WEAK)

# 一份快照只能用一次。連按兩下不該把次數扣成負的，也不該再動一次計時。
w28.undo_drink()
check("次數是 0 就不再退", w28.drinks, 0)

# 紀錄檔是只增不改的：drink 那一行必須還在，undo 是補上去的
_rows = [json.loads(x) for x in open(isl.EVENTS_PATH, encoding="utf-8") if x.strip()]
_mine = [r for r in _rows if r["day"] == w28.day]
check("原始的 drink 沒有被刪掉",
      any(r["event"] == "drink" for r in _mine), True)
check("補了一筆 undo", any(r["event"] == "undo" for r in _mine), True)

# 統計那邊要自己扣掉，而且回應率不能超過 100%
_days = dash.load_days(isl.EVENTS_PATH, 5)
_today = _days[w28.day]
check("統計的次數扣掉了", _today["drinks"], 0)
check("回應數也扣掉了（否則回應率會超過 100%）",
      _today["responded"] <= _today["reminds"], True)

# 重開程式之後沒有快照，只能退次數——但那也不能少做
w28b = fresh()
w28b.drinks = 3
w28b._undo = None                     # 模擬重開：快照不跨重啟
_kept = (w28b.active_s, w28b.interval_s)
w28b.undo_drink()
check("沒有快照時仍然退得掉次數", w28b.drinks, 2)
check("沒有快照時不亂動計時", (w28b.active_s, w28b.interval_s), _kept)

# 選單：次數是 0 就不該出現這一項（按下去不會有反應的項目比沒有更糟）
w28c = fresh()
w28c.drinks = 0
check("次數 0 時選單沒有這一項",
      any(it[0] and "退回" in it[0] for it in w28c._menu_items()), False)
w28c.drinks = 1
check("記過之後選單才有這一項",
      any(it[0] and "退回" in it[0] for it in w28c._menu_items()), True)

isl.EVENTS_PATH = _ev_save

print("\n29. 第二個實例不能靜靜消失")
# 事故：一支卡死的行程握著 mutex 八小時，而 main() 第一行 `return 0` 靜靜結束。
# 使用者整天沒有提醒，也沒有任何線索——工作管理員裡只是一個看起來正常的
# Sipbar.exe。**真正的傷害是「什麼都沒發生」，不是「打不開」。**
#
# 這裡刻意**不驗活性判斷**，因為程式刻意不做活性判斷。兩種判法都寫過也都
# 退掉了（心跳、本機管線），兩種都會在啟動那幾百毫秒內把一個健康的實例
# 判成屍體——理由寫在 single_instance_guard() 的 docstring，那段是這個決定
# 唯一的紀錄，動它之前先讀。
#
# 所以這一節驗的是：鎖還在、而且**話有講出來**。
# 用自己的鎖名，**絕對不要碰真實的那把**：機器上開著 Sipbar 是常態，
# 搶真實的鎖會讓這一節必定失敗，而且測試跑的那幾秒真的 Sipbar 會啟動不了。
_LKN = "SipbarTestLock-%d" % os.getpid()
check("沒有人佔著時拿得到", isl.single_instance_guard(_LKN), True)
check("已經有人佔著就拿不到", isl.single_instance_guard(_LKN), False)

# 訊息要一句涵蓋兩種情況：好好跑著的話講入口在哪，卡住的話講怎麼處理。
# 程式不分辨是哪一種，所以兩句都必須在。
_msg = []
_mb_save = isl._message_box
isl._message_box = lambda t: _msg.append(t)
isl.say_already_running()
isl._message_box = _mb_save
check("訊息真的送出去了（不是靜靜結束）", len(_msg), 1)
check("有講入口在哪", "螢幕頂端中央" in _msg[0], True)
check("也有講沒反應時怎麼辦", "工作管理員" in _msg[0], True)

_lock_w = fresh()                # 之後手動控制落檔，免得計時器在測試中途自己跳

# 定期落檔必須有自己的計時器，**不能放回 tick()**——那裡有三道 early return
# （暫停中、今天已達標、離開電腦），落檔在它們後面，所以那三種狀態下不會落檔。
# 那三段期間本來就沒有新的累積可以丟，所以不是資料遺失的問題；理由是落檔不該
# 依賴那三個判斷，否則之後任何人動了它們，落檔就跟著被改到而沒有人發現。
# 要驗「島一建出來就在跑」就不能用 fresh()，它為了測試穩定會把它停掉。
_beat_probe = isl.Island(dict(cfg))
check("落檔有自己的計時器且在跑", _beat_probe.beat_timer.isActive(), True)
check("落檔間隔就是 PERSIST_SECONDS",
      _beat_probe.beat_timer.interval(), isl.PERSIST_SECONDS * 1000)
_beat_probe.tick_timer.stop(); _beat_probe.frame.stop()
_beat_probe.hold_timer.stop(); _beat_probe.peek_timer.stop()
_beat_probe.beat_timer.stop()

# 暫停中 tick 會 early return，所以落檔絕不能只掛在 tick 上。
# 先把存檔時間推到很久以前，否則整段測試跑在同一秒內，「有沒有更新」比不出來。
_old = isl.load_state()
_old["saved_ts"] = "2020-01-01T00:00:00"
isl.save_state(_old)
_before = isl.load_state()["saved_ts"]
_lock_w.paused_until = datetime.now() + timedelta(hours=2)
for _ in range(30):
    _lock_w.tick()
check("暫停中 tick 完全不落檔", isl.load_state()["saved_ts"], _before)
_lock_w._persist()
check("而定期落檔照樣落得了檔", isl.load_state()["saved_ts"] != _before, True)
_lock_w.paused_until = None

print("\n30. 記帳失敗不能把功能一起帶走")
# 2026-08-19 的實況：使用者按了島，次數沒加、倒數沒歸零、確認訊息也沒出現，
# 他只會以為自己沒點到，然後再按一次。原因是 drink() 先記帳再改狀態。

# (a) log_event 本身不能往上炸。原本 os.makedirs() 在 try 之外，
#     資料夾建不出來就會拋 OSError 給呼叫端。
_dd_save, _evp_save = isl.DATA_DIR, isl.EVENTS_PATH
_blocker = os.path.join(TEST_DIR, "blocker")
open(_blocker, "w").close()          # 拿一個「檔案」當資料夾的上層，makedirs 一定失敗
isl.DATA_DIR = os.path.join(_blocker, "sub")
isl.EVENTS_PATH = os.path.join(isl.DATA_DIR, "events.jsonl")
_raised = None
try:
    isl.log_event("2026-01-01", "drink", drinks=1)
except Exception as e:                                    # noqa: BLE001
    _raised = type(e).__name__
check("資料夾建不出來時 log_event 不往上炸", _raised, None)
_raised = None
try:
    isl.save_state({"day": "2026-01-01", "saved_ts": "2026-01-01T00:00:00"})
except Exception as e:                                    # noqa: BLE001
    _raised = type(e).__name__
check("同樣的情況 save_state 也不往上炸", _raised, None)
isl.DATA_DIR, isl.EVENTS_PATH = _dd_save, _evp_save

# (b) 就算記帳那一行真的爆了，使用者按的那一下仍然要算數。
#     這是第二道防線：(a) 已經讓它不會爆，這裡防的是「哪天又有人在這條路上
#     加了會拋例外的東西」。
def _boom(*a, **k):
    raise RuntimeError("模擬記帳爆炸")

_w30 = fresh()
_w30.active_s = 1234.0
_w30._last_drink_at = -999.0         # 繞開防連點，否則這一下會被當成手滑
_orig_log = isl.log_event
isl.log_event = _boom
try:
    _w30.drink()
except Exception as e:                                    # noqa: BLE001
    pass                              # 例外照樣往上走沒關係，重點是狀態已經改了
finally:
    isl.log_event = _orig_log
check("記帳爆炸時次數仍然有加", _w30.drinks, 1)
check("記帳爆炸時倒數仍然歸零", _w30.active_s, 0.0)

print("\n31. 寫檔失敗不能繼續無聲")
# 2026-08-19 的實況：程式活著、島照常提醒、倒數照常走，而補水一次都沒有被記錄，
# 整整 3.5 小時。使用者不會發現（畫面上一切正常），不發現就不會回報，
# 於是這種災情永遠不會有人知道。吞掉例外是對的，但不能連「發生過」都不留。
_st = isl.settings


def _reset_writes():
    for _k in ("config", "state", "events"):
        _st.note_write(_k, True)


_reset_writes()
check("一開始沒有問題", _st.write_trouble(), False)
for _ in range(_st.WRITE_FAIL_THRESHOLD - 1):
    _st.note_write("events", False)
# 偶發失敗很常見（防毒會在檔案剛寫完時開掃描用的 handle），第一次就喊會變狼來了
check("還沒到門檻不出聲", _st.write_trouble(), False)
_st.note_write("events", False)
check("連續失敗到門檻就示警", _st.write_trouble(), True)
check("而且說得出是哪一個檔案", _st.failing_writes(), ["events"])
_st.note_write("events", True)
check("那個檔案恢復就不再示警", _st.write_trouble(), False)

# **這一條是整節的重點。** 第一版用一個共用的計數器，任何一次成功就歸零，
# 於是「只有 events.jsonl 壞掉」永遠達不到門檻：drink() 是記錄緊接著存檔，
# 記錄失敗的下一行就被存檔的成功抹掉；就算不補水，定期落檔每 60 秒也會抹一次。
# 實測過的後果：連按十次補水，十筆全部遺失，計數器從頭到尾 0、島上顯示已達標。
# 而那正是 CHANGELOG 拿來當例子的情境（檔案被雲端同步或防毒單獨鎖住）。
_reset_writes()
for _ in range(_st.WRITE_FAIL_THRESHOLD * 4):
    _st.note_write("events", False)
    _st.note_write("state", True)          # 另外兩個一直是好的，模擬單檔被鎖住
    _st.note_write("config", True)
check("只有紀錄檔壞掉時照樣示警（共用計數器會漏掉這個）",
      _st.write_trouble(), True)
check("而且指得出是紀錄檔", _st.failing_writes(), ["events"])
_reset_writes()

# 真的讓寫檔失敗，確認計數器接得上——不能只有計數函式自己會動
_dd2, _evp2 = isl.DATA_DIR, isl.EVENTS_PATH
isl.DATA_DIR = os.path.join(_blocker, "sub2")     # _blocker 是第 30 節建的那個檔案
isl.EVENTS_PATH = os.path.join(isl.DATA_DIR, "events.jsonl")
for _ in range(_st.WRITE_FAIL_THRESHOLD):
    isl.log_event("2026-01-01", "drink", drinks=1)
check("log_event 真的寫不進去時會被數到", _st.write_trouble(), True)
isl.DATA_DIR, isl.EVENTS_PATH = _dd2, _evp2

# 島上兩條路徑都要說得出口。
# 先建島再製造失敗：Island.__init__ 最後會落檔一次，成功的話計數就歸零了
_w31 = fresh()
_reset_writes()
_w31.paused_until = datetime.now() + timedelta(hours=2)
for _ in range(_st.WRITE_FAIL_THRESHOLD):
    _st.note_write("events", False)
# 探頭看到的那一行。示警要蓋過「暫停中」——暫停是使用者自己按的，他知道；
# 存不進去他不知道，所以那一則比較急。
check("探頭時說得出來", _w31._status_sub(), "紀錄存不進去")
# **島真的掛在畫面上時走的是另一條分支。** 那才是使用者唯一會盯著看的時候，
# 而底下那個「今天 N/M 次」在存不進去的時候是假的。
check("島跳出來時也說得出來", _w31._reminding_sub(), "紀錄存不進去")
_reset_writes()
check("恢復之後兩條都不再示警",
      ("紀錄存不進去" in _w31._status_sub(),
       "紀錄存不進去" in _w31._reminding_sub()), (False, False))
_w31.paused_until = None

print("\n32. 夜間模式要在早上結束，不能拖到宣告的起床時間")
# 使用者的情境：起床設 10 點，早上 7 點坐在電腦前，間隔仍然是 86 分
# （75 × 1.45），而畫面刻意不解釋（見 _status_sub），只看得到一個沒有原因的
# 長倒數。舊寫法把夜間的結束綁在「習慣起床時間」這個**宣告值**上；
# 放慢的理由是「睡前灌水會半夜起來上廁所」，那個理由早上完全不成立。
_saved_hours = (w.cfg["late_night_start_hour"], w.cfg["day_rollover_hour"])
w.cfg["late_night_start_hour"] = 21
w.cfg["day_rollover_hour"] = 10                 # 宣告「我 10 點起床」
check("夜間是 21:00 到清晨換日（5 點）",
      [h for h in range(24) if w._is_late(h)], [0, 1, 2, 3, 4, 21, 22, 23])
check("起床宣告 10 點，早上 7 點不再是夜間", w._is_late(7), False)
check("凌晨 4 點仍然是夜間", w._is_late(4), True)
w.cfg["day_rollover_hour"] = 3
check("起床宣告改成 3 點，範圍一樣不受影響",
      [h for h in range(24) if w._is_late(h)], [0, 1, 2, 3, 4, 21, 22, 23])

# 極端設定不能變成「整天都是夜間」。早上 6 點才睡的人，起點被推導成 3 點，
# 舊寫法的 `hour >= 3 or hour < 5` 涵蓋全部 24 小時，提醒從此永遠放慢。
w.cfg["late_night_start_hour"] = 3
check("起點落在換日之後：只有 3 點到 5 點是夜間",
      [h for h in range(24) if w._is_late(h)], [3, 4])
w.cfg["late_night_start_hour"] = 5
check("起點正好等於換日：沒有夜間", [h for h in range(24) if w._is_late(h)], [])
w.cfg["late_night_start_hour"], w.cfg["day_rollover_hour"] = _saved_hours

# 範圍對了還不夠：昨晚 23:00 擲出的那一段間隔本身還是夜間長度，不重擲的話
# 它會一路跟到早上。這件事不必另外寫程式——夜間的結束與換日是同一個時刻，
# 而 tick() 的換日分支本來就會重擲。這一條守的是那個巧合不被改掉。
w._is_late = lambda hour=None: True
w.interval_s = w._roll_interval()
_night_min = w.interval_s / 60
w._is_late = lambda hour=None: False
w.day = "2000-01-01"                            # 假裝跨過清晨那個換日
w.tick()
_morning_min = w.interval_s / 60
del w._is_late
# 抖動 ±15%：白天最長 86.25 分，夜間最短 92.4 分，中間那條線劃在 90。
check(f"夜間擲出 {_night_min:.0f} 分，比白天長", _night_min > 90, True)
check(f"換日之後重擲成 {_morning_min:.0f} 分，回到白天的長度",
      _morning_min < 90, True)

print("\n33. 第一次達標要講一次「紀錄在哪裡」")
# 紀錄視窗（連續天數、熱圖、成就）做得比島本身完整，而唯一的入口是右鍵——
# 一個沒有任何視覺提示的動作。第一次達標是這句話最該出現的時刻：使用者第一次
# 真的有東西可看，而且他正盯著島。
_cfg33 = dict(cfg)
_cfg33["records_hinted"] = False
w33 = isl.Island(_cfg33)
w33.tick_timer.stop(); w33.frame.stop(); w33.hold_timer.stop()
w33.peek_timer.stop(); w33.beat_timer.stop()
w33.drinks = _cfg33["daily_target_drinks"] - 1
sip(w33)                                        # 喝下達標的那一口
check("主字仍然是達標", w33.message, "今天達標了")
check("小標換成指示", w33.sub_message, "右鍵可以看紀錄")
check("提示過就記下來", w33.cfg["records_hinted"], True)
check("而且寫回設定檔",
      json.load(io.open(ap.CONFIG_PATH, encoding="utf-8"))["records_hinted"], True)
# 1.8 秒是為「喝了，還剩 N 次」調的，那句話使用者早就知道，掃一眼就夠。
# 一句他沒看過的指示要讀完才有用。
check("停留拉長到口渴那一階的長度",
      w33.hold_timer.interval(), int(_cfg33["thirsty_hold_seconds"] * 1000))

# 第二次達標不能再講。講第二次就變成他每天都要略過一次的東西，
# 而那正是這個工具最不想變成的樣子。
w33.drinks = _cfg33["daily_target_drinks"] - 1
sip(w33)
check("第二次達標不再提示", w33.sub_message != "右鍵可以看紀錄", True)
check("停留回到原本的閃一下",
      w33.hold_timer.interval(), int(_cfg33["satisfied_flash_seconds"] * 1000))

# 沒達標的那些補水完全不受影響：提示只掛在達標那一刻。
_cfg33b = dict(cfg)
_cfg33b["records_hinted"] = False
w33b = isl.Island(_cfg33b)
w33b.tick_timer.stop(); w33b.frame.stop(); w33b.hold_timer.stop()
w33b.peek_timer.stop(); w33b.beat_timer.stop()
w33b.drinks = 0
sip(w33b)
check("還沒達標時不提示", w33b.sub_message != "右鍵可以看紀錄", True)
check("也不會把旗標用掉", w33b.cfg["records_hinted"], False)

print("\n34. 主字帶次數：每一句都放得下，而且不會每 5 秒換一句")
# 使用者的觀察：「我自己用下來容易忽略喝水提醒」。習慣化的解藥是變化，
# 所以主字會帶上還差幾次，句型也多了一批。變化有兩個代價，這一節守這兩個。
#
# 代價一：「最長的那一句」沒辦法再用眼睛掌握。放不下就被省略號截掉。
# 上限要用**最小的那台機器**驗：1366 的筆電上藥丸最寬 478px，而跑測試這台是
# 3440（上限 700px）。只驗這台等於沒驗。
_real_max = w2._max_pill_w
w2._max_pill_w = lambda: 1366 * isl.PILL_SCREEN_FRAC
_saved34 = (w2.cfg["daily_target_drinks"], w2.state, w2.drinks,
            w2.message, w2.sub_message)
w2.cfg["daily_target_drinks"] = 12          # 進度點最多，文字空間最小
_cut, _seen = None, set()
for _st in isl.REMINDING:
    w2.state = _st
    for _d in (0, 5, 11):                   # 今天還沒喝、中段、只差最後一次
        w2.drinks = _d
        for _line in w2._message_pool():
            if _line in _seen:
                continue
            _seen.add(_line)
            _av, _pw = _avail_for(_line, "連續 128 天")
            _need = QFontMetrics(w2._f_title).horizontalAdvance(_line)
            if _need > _av and _cut is None:
                _cut = f"「{_line}」需要 {_need:.0f}px / 可用 {_av:.0f}px"
print(f"       掃過 {len(_seen)} 句（3 個狀態 × 3 個進度，目標 12 次、1366 筆電）")
check("每一句主字都放得下", _cut, None)
w2._max_pill_w = _real_max

# 代價二：抽籤如果每次呼叫都重抽，探頭時 tick() 每 5 秒就換一句話。
# 先前寬度固定所以不太明顯，藥丸改成跟著文字走之後會連寬度一起抖。
w2.cfg["daily_target_drinks"] = 9
w2.state, w2.drinks, w2._msg_cache = isl.THIRSTY, 2, None
w2._refresh_message()
_first = w2.message
_stable = True
for _ in range(30):
    w2._refresh_message()
    _stable = _stable and w2.message == _first
check("同一個狀態與次數，主字不會每次重抽", _stable, True)
w2.drinks = 3
w2._refresh_message()
check("次數變了才重抽", w2._msg_cache[0][1], 3)
# 打招呼會直接寫掉 message（不走抽籤）。只比對鑰匙的話，回到一般狀態時
# 會把「嗨！」當成抽到的結果留著。
w2._set_text("嗨！", "游標移至螢幕上緣中央可呼叫")
w2._refresh_message()
check("打招呼之後會回到抽到的那一句", w2.message == "嗨！", False)
(w2.cfg["daily_target_drinks"], w2.state, w2.drinks,
 w2.message, w2.sub_message) = _saved34

print("\n35. 提醒時偶爾帶一句提示")
# 使用者的觀察：「容易忽略喝水提醒」。帶數字的主字解決了「每天同一句」，
# 但那仍然是同一類話。提示是唯一一段他沒看過的內容。
#
# 份量要壓得很小：小標平常顯示連續天數，而那是這個工具最重要的動機數字。
_saved35 = (w2.cfg["daily_target_drinks"], w2.state, w2.drinks,
            w2.message, w2.sub_message, w2._tip)

# 每一句都要放得下，而且是用最小的那台機器驗（1366 筆電、目標 12 次時，
# 小標只放得下 13 個中文字）。被截掉的提示比沒有提示更糟：它看起來像壞掉。
_real_max = w2._max_pill_w
w2._max_pill_w = lambda: 1366 * isl.PILL_SCREEN_FRAC
w2.cfg["daily_target_drinks"] = 12
w2.state = isl.THIRSTY
_too_long = None
for _tip in isl.TIPS:
    _av, _pw = _avail_for("口渴了", _tip)
    _need = QFontMetrics(w2._f_sub).horizontalAdvance(_tip)
    if _need > _av and _too_long is None:
        _too_long = f"「{_tip}」需要 {_need:.0f}px / 可用 {_av:.0f}px"
print(f"       量過 {len(isl.TIPS)} 句提示（目標 12 次、1366 筆電）")
check("每一句提示都放得下", _too_long, None)
w2._max_pill_w = _real_max

# 一天最多兩次。每多一次就少看一次連續天數。
w2.cfg["daily_target_drinks"] = 9
_counts = []
for _ in range(40):
    w2._roll_tip_slots()
    _n = 0
    for _d in range(9):
        w2.drinks = _d
        w2._maybe_pick_tip()
        _n += 1 if w2._tip else 0
    _counts.append(_n)
check("一天的次數固定是 TIPS_PER_DAY", set(_counts), {isl.TIPS_PER_DAY})

# 落點要隨機。固定在第一次的話它自己就變成可預測的東西，
# 而可預測正是這整件事要對抗的。
_slots = set()
for _ in range(60):
    w2._roll_tip_slots()
    _slots |= w2._tip_slots
check("落點不是每天都同一次", len(_slots) > isl.TIPS_PER_DAY, True)

# 抽完一輪才重洗：使用者對「又是這句」的敏感度遠高於「這句我上個月看過」。
w2._tip_deck = []
_drawn = [w2._draw_tip() for _ in range(len(isl.TIPS))]
check("一輪之內不重複", len(set(_drawn)), len(isl.TIPS))

# 探頭是「我要查狀態」，不是「我要看知識」。提示只在島自己跳出來時出現。
w2.state, w2.drinks, w2._tip = isl.NORMAL, 2, isl.TIPS[0]
check("探頭時不給提示", isl.TIPS[0] in w2._status_sub(), False)

# 寫不進去要蓋過一切，包含提示——那是使用者唯一會知道自己在掉資料的地方。
w2.state = isl.THIRSTY
for _ in range(ap.WRITE_FAIL_THRESHOLD):
    ap.note_write("events", False)
check("紀錄存不進去時蓋過提示", w2._reminding_sub(), "紀錄存不進去")
ap.note_write("events", True)
check("恢復之後提示回來", w2._reminding_sub(), isl.TIPS[0])

(w2.cfg["daily_target_drinks"], w2.state, w2.drinks,
 w2.message, w2.sub_message, w2._tip) = _saved35

print("\n99. 整支測試不能碰到使用者真實的資料檔")
# Qt 會吞掉 slot 裡拋出的例外——只把 traceback 印到 stderr 然後繼續跑。
# 所以光靠 settings 的防線拋例外還不夠：自動化跑完照樣顯示「全部通過」，
# 而它其實已經闖進真實資料。這一條把印出來的 traceback 變成可斷言的事實。
check("防線沒有攔截到任何寫入", isl.settings.real_write_violations(), [])

print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 項失敗：{fails}"))
sys.exit(1 if fails else 0)

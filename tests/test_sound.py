# -*- coding: utf-8 -*-
"""提示音：音檔本身、音量上限、播放的旗標、失敗時的沉默。

## 為什麼音量要用測試守

`PEAK` 是這整個功能唯一守不住就會壞掉的參數。winsound 用系統音量播放，
程式在播的時候沒有任何辦法把它調小——**檔案本身的振幅就是音量**。

而且失敗的方式很不對稱：太小聲只是沒效果，太大聲會嚇到人，
而被嚇到的人第一件事是去把它關掉。所以上限要釘死。

## 為什麼要比對「重新算一次的結果」

這一條守的是專案的規矩：沒有外來素材。字體、圖示、示意圖全部是程式產的，
音效也一樣（見 tools/build_sound.py 開頭）。

比對 bytes 同時守住兩件事：commit 進去的音檔真的是那支工具產的
（沒有人從音效庫抓一個塞進來），而且沒有過期（改了合成參數卻忘記重跑）。

用法：python tests/test_sound.py
"""
import os
import sys
import time
import wave

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import build_sound  # noqa: E402
import sound  # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(("  ok  " if ok else "  FAIL") + f"  {label}: {got!r}"
          + ("" if ok else f"  (預期 {want!r})"))
    if not ok:
        fails.append(label)


NAMES = (sound.WEAK, sound.COLLAPSED)

# 音量上限。0.26 是 build_sound.PEAK，留一點餘裕給正規化的取整誤差。
# 上限存在的理由見模組開頭；不能因為「聽不太到」就往上調——
# 這個聲音出現的時機是已經被忽略 15 分鐘，它要的是被注意到，不是壓過別的東西。
PEAK_CEILING = 0.30
# 長度上限。超過一秒的提示音會蓋到使用者正在聽的東西（會議、影片、剪輯的音軌）。
MAX_SECONDS = 1.2
MIN_SECONDS = 0.30


print("\n1. 每個宣告的名字都要有對應的音檔")
for name in NAMES:
    check(f"{name}.wav 存在", os.path.exists(sound.path(name)), True)
# 反過來也要成立：工具產的每一個都要被用到，否則就是躺在發布包裡的死檔案。
check("工具產的音檔與程式用的名字一致",
      sorted(build_sound.VOICES.keys()), sorted(NAMES))


print("\n2. 格式：單聲道 16-bit PCM")
for name in NAMES:
    with wave.open(sound.path(name), "rb") as f:
        check(f"{name} 聲道", f.getnchannels(), 1)
        check(f"{name} 位元深度（bytes）", f.getsampwidth(), 2)
        check(f"{name} 取樣率", f.getframerate(), build_sound.SR)
        # winsound 只吃 PCM。壓縮過的 WAV 會靜默播不出來。
        check(f"{name} 未壓縮", f.getcomptype(), "NONE")


print("\n3. 音量與長度都在上限之內")
for name in NAMES:
    with wave.open(sound.path(name), "rb") as f:
        n = f.getnframes()
        raw = f.readframes(n)
        secs = n / f.getframerate()
    peak = max(abs(int.from_bytes(raw[i:i + 2], "little", signed=True))
               for i in range(0, len(raw), 2)) / 32767
    check(f"{name} 不是靜音", peak > 0.05, True)
    check(f"{name} 尖峰不超過 {PEAK_CEILING}", peak <= PEAK_CEILING, True)
    check(f"{name} 長度在 {MIN_SECONDS}–{MAX_SECONDS} 秒之間",
          MIN_SECONDS <= secs <= MAX_SECONDS, True)
    print(f"        （{name}：{secs:.2f} 秒，尖峰 {peak:.2f}）")


print("\n4. 音檔就是工具產出來的那一份，沒有被換掉也沒有過期")
for name in NAMES:
    with wave.open(sound.path(name), "rb") as f:
        on_disk = f.readframes(f.getnframes())
    fresh = build_sound.render(build_sound.VOICES[name]).tobytes()
    check(f"{name} 與重新合成的結果一致", on_disk == fresh, True)


print("\n5. 兩個音的方向相反")
# 上行是招呼，下行是倒下去。同一種音色講兩句不同的話，這是它們唯一的差別，
# 所以要守住——把 collapsed 也改成上行的話，兩級升級就聽不出分別了。
weak_freqs = [f for _, f, _, _, _ in build_sound.VOICES[sound.WEAK]]
coll_freqs = [f for _, f, _, _, _ in build_sound.VOICES[sound.COLLAPSED]]
check("weak 往上", weak_freqs == sorted(weak_freqs), True)
check("collapsed 往下", coll_freqs == sorted(coll_freqs, reverse=True), True)
check("collapsed 整體比 weak 低", max(coll_freqs) < min(weak_freqs), True)


print("\n6. 播放用的旗標")
# SND_NODEFAULT 是這裡最重要的一個。少了它，播不出來時 Windows 會播
# **系統預設音**——那個聲音又大又不是我們的，比沒有聲音糟得多。
calls = []


class FakeWinsound:
    SND_FILENAME, SND_ASYNC, SND_NODEFAULT = 0x20000, 0x0001, 0x0002

    def PlaySound(self, path, flags):       # noqa: N802  （模仿 winsound 的命名）
        calls.append((path, flags))


fake = FakeWinsound()
sound._winsound, sound._probed = fake, True

check("播得出去", sound.play(sound.WEAK), True)
check("呼叫了一次", len(calls), 1)
_, flags = calls[0]
check("非阻塞（SND_ASYNC）", bool(flags & fake.SND_ASYNC), True)
check("失敗時不播系統預設音（SND_NODEFAULT）",
      bool(flags & fake.SND_NODEFAULT), True)
check("用檔名播（SND_FILENAME）", bool(flags & fake.SND_FILENAME), True)


print("\n7. 播不出來一律沉默，不能拋例外")
# 提醒本身已經在畫面上了，聲音只是附加的一層。這一層壞掉不該讓提醒出問題，
# 所以每一條失敗路徑都必須是「回 False」而不是「炸開」。
check("檔案不存在", sound.play("這個名字沒有對應的檔案"), False)


class ExplodingWinsound:
    SND_FILENAME, SND_ASYNC, SND_NODEFAULT = 0x20000, 0x0001, 0x0002

    def PlaySound(self, path, flags):       # noqa: N802
        raise RuntimeError("音效裝置不見了")


sound._winsound = ExplodingWinsound()
check("播放本身出錯", sound.play(sound.WEAK), False)

sound._winsound = None                      # 模擬非 Windows：import winsound 失敗
check("沒有 winsound（非 Windows）", sound.play(sound.WEAK), False)


print("\n8. 自訂音效：放檔案就換掉，壞檔要退回內建")
# 這一組守的是「不會沉默地失效」。自訂音效最容易發生的事是使用者把 mp3 改名
# 成 .wav，而如果程式照播、winsound 靜靜失敗，他會等 15 分鐘然後什麼都沒有，
# 也不知道原因。壞檔一定要回到內建，而且要能被回報出來。
import shutil  # noqa: E402
import tempfile  # noqa: E402

SANDBOX = tempfile.mkdtemp(prefix="sipbar_sound_")
sound.USER_DIR = SANDBOX                    # 絕對不要指到使用者真實的資料夾
BUILTIN = os.path.join(ROOT, "assets", "sound")

check("沒放自訂檔時用內建", sound.path(sound.WEAK),
      os.path.join(BUILTIN, "weak.wav"))
check("沒放的時候不列任何自訂檔", sound.custom_files(), [])

# 放一個真的 WAV（直接拿內建的當作使用者的檔案）
shutil.copy(os.path.join(BUILTIN, "collapsed.wav"), sound.user_path(sound.WEAK))
check("放了就優先用自訂的", sound.path(sound.WEAK), sound.user_path(sound.WEAK))
check("自訂檔判定為可播", sound.custom_files(), [(sound.WEAK, True)])
# 只換一個是允許的：另一個要繼續用內建，不能一起被拖下去
check("沒換的那個仍然是內建", sound.path(sound.COLLAPSED),
      os.path.join(BUILTIN, "collapsed.wav"))

# 把 mp3 改名成 .wav —— 這是真正會發生的錯誤
with open(sound.user_path(sound.COLLAPSED), "wb") as f:
    f.write(b"ID3\x04\x00\x00\x00\x00\x00\x00not really a wav")
check("改名的 mp3 判定為不可播", sound.custom_files(),
      [(sound.WEAK, True), (sound.COLLAPSED, False)])
check("壞檔退回內建，不是靜音", sound.path(sound.COLLAPSED),
      os.path.join(BUILTIN, "collapsed.wav"))

# 刪掉就回到內建，不必改任何設定——這是「檔案在不在就是全部的狀態」的意思
os.remove(sound.user_path(sound.WEAK))
check("刪掉自訂檔就回到內建", sound.path(sound.WEAK),
      os.path.join(BUILTIN, "weak.wav"))

# ---- 設定頁「選擇」走的那條路：驗格式、複製、還原 ----
_pick_dir = tempfile.mkdtemp(prefix="sipbar_pick_")
_good = os.path.join(_pick_dir, "我的鈴聲.wav")
shutil.copy(os.path.join(BUILTIN, "weak.wav"), _good)
_fake = os.path.join(_pick_dir, "其實是 mp3.wav")
with open(_fake, "wb") as f:
    f.write(b"ID3\x04\x00\x00not a wav at all")

check("選到真的 WAV 就裝起來", sound.install(sound.WEAK, _good), True)
check("裝完之後播的是自訂的", sound.path(sound.WEAK), sound.user_path(sound.WEAK))

# 驗不過的話**什麼都不能動**。覆蓋成一個播不出來的檔案，
# 會讓一個原本正常的音效無聲地消失——那比拒絕安裝糟得多。
check("選到假的 WAV 不裝", sound.install(sound.WEAK, _fake), False)
check("而且上一次裝好的還在", sound.path(sound.WEAK), sound.user_path(sound.WEAK))
check("上一次裝的仍然是可播的", dict(sound.custom_files())[sound.WEAK], True)
check("檔案不存在也不裝",
      sound.install(sound.WEAK, os.path.join(_pick_dir, "沒這個檔.wav")), False)

# 還原：只刪我們複製過來的那份，使用者的原檔不能被碰到
check("還原", sound.remove(sound.WEAK), True)
check("還原後回到內建", sound.path(sound.WEAK), os.path.join(BUILTIN, "weak.wav"))
check("使用者挑的原檔沒有被刪掉", os.path.exists(_good), True)
check("重複還原不會拋例外", sound.remove(sound.WEAK), False)
shutil.rmtree(_pick_dir, ignore_errors=True)

# 讀不到的路徑不能讓 _is_wav 炸開（權限、檔案正被佔用、路徑含空字元）
check("路徑異常時判定為不可播", sound._is_wav("\x00這個路徑不合法"), False)
check("資料夾不是檔案", sound._is_wav(SANDBOX), False)

# 說明檔：按了「開啟」看到空資料夾等於沒有說明
sound.ensure_user_dir()
_readme = os.path.join(SANDBOX, sound.README_NAME)
check("建資料夾時放了說明", os.path.exists(_readme), True)
with open(_readme, encoding="utf-8") as f:
    _txt = f.read()
check("說明寫了兩個檔名", ("weak.wav" in _txt) and ("collapsed.wav" in _txt), True)
# 不覆蓋：使用者可能在裡面加了自己的筆記
with open(_readme, "a", encoding="utf-8") as f:
    f.write("\n使用者自己加的一行\n")
sound.ensure_user_dir()
with open(_readme, encoding="utf-8") as f:
    check("再次開啟不會覆蓋說明", "使用者自己加的一行" in f.read(), True)

shutil.rmtree(SANDBOX, ignore_errors=True)
sound.USER_DIR = os.path.join(SANDBOX, "已刪除")   # 後面的段落一律看不到自訂檔


print("\n9. 引導要先告知會有聲音")
# 使用者的要求：一個平常完全安靜的工具突然出聲，沒有預告的話第一反應是
# 「哪來的聲音」，而那一刻他要找的是關掉的方法，不是水。
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication(sys.argv)    # noqa: F841
import onboard  # noqa: E402
import settings as appsettings  # noqa: E402

# 用寫的沒有用，要當場放給他聽。所以驗的是「試一次」那一頁的行為，
# 不是某一條文案有沒有提到聲音。
_played = []
_real = sound.play
sound.play = lambda n: _played.append(n) or True

win = onboard.OnboardWindow()
win.frame.stop()
check("點之前音效那一段是藏著的", win.sound_block.isVisible(), False)
check("點之前不出聲", _played, [])

win.show()
win._go(win.page_index["try"])
win._on_tried()
check("點完就長出來", win.sound_block.isVisible(), True)
check("而且開關就在同一個畫面上", win.sound_on.isVisibleTo(win.sound_block), True)
check("說明講的是剛剛那一聲", "剛剛" in onboard.TRY_SOUND, True)
# 只說「我會叫」是威脅，附上出口才是告知。這一頁的出口是底下那個開關，
# 文案也要指得到它。
check("同一段就給出關掉的方法", "關掉" in onboard.TRY_SOUND, True)

# 聲音是延一拍才播的：跟畫面同時出聲會被讀成「我按下去的音效」
check("還沒到那一拍時不出聲", _played, [])
_app.processEvents()
_t0 = time.time()
while not _played and time.time() - _t0 < 3.0:
    _app.processEvents()
check("一拍之後放一次升級的聲音", _played, [sound.WEAK])

# 已經關掉的人重看導覽，不該被播回臉上
_played.clear()
win2 = onboard.OnboardWindow(sound_on=False)
win2.frame.stop()
win2.show()
win2._go(win2.page_index["try"])
win2._on_tried()
_t0 = time.time()
while time.time() - _t0 < 0.9:
    _app.processEvents()
check("關掉的人重看導覽不出聲", _played, [])
# 但想聽的話扳一下就有——這一頁沒有「試聽」，開關就是試聽
win2.sound_on.set_on(True)
check("在這一頁扳開會放一次", _played, [sound.WEAK])

# 引導的選擇要真的被帶出去。沒有這一步，那個開關就只是個裝飾。
_result = {}
win2.finished.connect(_result.update)
win2.sound_on.set_on(False)
win2._emit_finish()
check("按下開始會把音效的選擇帶出去", _result.get("sound_enabled"), False)

sound.play = _real
win.close(); win2.close()
check("預設是開著的", appsettings.DEFAULTS["sound_enabled"], True)

# 顯示用的檔名不能是巢狀的可變值。DEFAULTS 是 dict() 淺複製出去的，
# 巢狀 dict 會被所有設定共用，改一個人的設定就改到預設值本身。
for _k in ("sound_name_weak", "sound_name_collapsed"):
    check(f"{_k} 是不可變的預設值",
          isinstance(appsettings.DEFAULTS[_k], str), True)


print("\n99. 這支測試不能碰到使用者真實的資料檔")
check("防線沒有攔截到任何寫入", appsettings.real_write_violations(), [])

print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 項失敗：{fails}"))
sys.exit(1 if fails else 0)

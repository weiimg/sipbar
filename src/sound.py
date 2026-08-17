# -*- coding: utf-8 -*-
"""升級時的提示音。

## 聲音在這個工具裡的位置

升級是一道階梯：換色 -> 變大 -> 不再自己消失 -> 出聲。
聲音是最後一階，所以它**只在被忽略之後響**，不在每次提醒時響。

差別不只是次數。每次提醒都響的話，一天七聲同樣的聲音，兩天就會被自動過濾掉
——而那個過濾會連帶讓人對整個工具脫敏，比沒有聲音更糟。
只在升級時響，平常完全安靜，聲音才留得住它的意思。

實際的觸發點在 `island.Island.tick()` 的升級分支，跟 log_event 排在一起。
**刻意不寫在 `_enter()` 裡面**：啟動時會接回上次的狀態（見 island.main()），
那條路徑也會 `_enter(WEAK)`，寫在裡面的話每次開機都會對著使用者響一聲。

## 為什麼是 winsound

Python 內建，零額外相依。這個程式本來就只跑 Windows（閒置偵測、單一實例鎖、
開機自啟都是 Win32），所以「只有 Windows 能用」在這裡不是限制。

替代方案是 QtMultimedia：要多帶 PySide6-Addons（幾十 MB），而且這台開發機
上根本沒裝。為了一個提示音把發布包從 47MB 變成 80MB 不值得。

macOS 版要另外接（`afplay` 或 NSSound），到時候在 `_backend()` 裡分流。

## 失敗一律沉默

沒有音效卡、檔案被防毒隔離、使用者把系統音效關成靜音——這些都不該讓提醒
本身出問題。島已經滑下來了，聲音只是附加的一層，播不出來就算了。

所以這裡沒有錯誤回報，也沒有寫進 crash.log：那會變成每次提醒都往硬碟寫一筆
使用者無能為力的訊息。

## 自訂音效：選檔案，但存的是複製過來的那一份

設定頁用系統的檔案選擇器讓使用者挑檔，挑完**複製一份**進
`%LOCALAPPDATA%\\Sipbar\\sound\\`，之後播的都是那一份。兩個音各自獨立，
只換一個也可以；按「還原」就把複製的那份刪掉，回到內建。

為什麼不是把選到的路徑存進 config.json：那條路會多出一整排只有它會有的問題
——原檔被搬走、改名、隨身碟拔掉、專案資料夾整個移位，聲音就**沉默地**不見了，
而設定頁看起來還是好好的。複製過來之後，這個檔案的生死由這個程式自己負責，
**檔案在不在就是全部的狀態**。

config.json 裡只留一個東西：使用者當初挑的檔名，純粹拿來顯示。它跟實際播放
無關，掉了最多是那一列顯示「自訂」而不是「我的鈴聲.wav」——不會影響任何行為。

直接把檔案丟進那個資料夾也算數（檔名要是 `weak.wav` 或 `collapsed.wav`），
選擇器只是把這件事做得不必記檔名。
"""
import os
import shutil

import settings

# 檔名，也是 play() 的參數。跟 island 的狀態常數同名不是巧合，但刻意不直接
# 用 `state.lower()` 去組——那樣檔案與狀態就綁死了，改一個狀態名字會讓聲音
# 無聲地消失（play() 是沉默失敗的，不會有人發現）。
WEAK = "weak"
COLLAPSED = "collapsed"

SOUND_DIR = os.path.join(settings.resource_dir(), "assets", "sound")
# 自訂音效放這裡。跟 config.json、events.jsonl 同一個資料夾底下，
# 所以設定頁「資料位置」那個「開啟」也到得了。
USER_DIR = os.path.join(settings.DATA_DIR, "sound")

_winsound = None
_probed = False


def _backend():
    """拿到 winsound，拿不到就回 None。只探一次。"""
    global _winsound, _probed
    if not _probed:
        _probed = True
        try:
            import winsound
            _winsound = winsound
        except ImportError:
            _winsound = None            # 不是 Windows
    return _winsound


def _is_wav(p):
    """前 12 bytes 是不是 RIFF/WAVE 容器。

    **刻意不用 `wave` 模組解析。** Python 的 wave 對 WAVE_FORMAT_EXTENSIBLE 與
    浮點格式會直接拋例外（「unknown format: 65534」），而那兩種 Windows 播得
    出來——拿它當守門員會把剪輯軟體匯出的正常檔案判成壞檔，然後對著使用者
    說「格式不支援」。那比不檢查更糟：它是錯的，而且看起來很權威。

    真正會發生的錯誤是把 mp3／m4a 改名成 .wav（副檔名對了、內容不是），
    檢查容器就攔得到，而且不會誤判。
    """
    try:
        with open(p, "rb") as f:
            head = f.read(12)
        return head[:4] == b"RIFF" and head[8:12] == b"WAVE"
    except Exception:
        return False


def user_path(name):
    """自訂音檔該放的位置。"""
    return os.path.join(USER_DIR, name + ".wav")


def custom_files():
    """使用者放了哪些自訂音檔。回 [(名字, 能不能播), ...]，沒放的不列。

    只回事實，不組文字——顯示成什麼由 stats_window 決定。
    這條分工跟 dashboard／stats_window 一樣：算的不畫，畫的不算。
    """
    out = []
    for name in (WEAK, COLLAPSED):
        p = user_path(name)
        if os.path.exists(p):
            out.append((name, _is_wav(p)))
    return out


def path(name):
    """要播哪個檔。自訂的優先，沒有或不能播就回內建的。

    每次重算不做快取：使用者換了檔案就該立刻生效，
    而且測試才能把 SOUND_DIR／USER_DIR 指到別處。

    逐個 name 判斷，所以只換一個也可以——放了 weak.wav、沒放 collapsed.wav，
    就是自訂的招呼聲配內建的倒地聲。
    """
    custom = user_path(name)
    if os.path.exists(custom) and _is_wav(custom):
        return custom
    return os.path.join(SOUND_DIR, name + ".wav")


# 開啟自訂資料夾時一起放進去的說明。
#
# 為什麼要有這個檔：按了「開啟」之後看到一個空資料夾，接下來要做什麼是猜的。
# 設定頁那一列的寬度只夠寫檔名，寫不下「格式要求」與「怎麼還原」。
#
# 用 .txt 不用 .md：這是給人在檔案總管裡雙擊的，記事本打開就是最終樣貌。
README_NAME = "說明.txt"
README_TEXT = """自訂提醒音效

平常不必用到這個資料夾——設定頁的「提醒音效」底下有「選擇」，挑完會自動
複製進來。這份說明是給想直接放檔案的人看的。

把音檔放進這個資料夾，檔名必須是下面兩個之一：

    weak.wav        被忽略 15 分鐘時播（內建版是往上的兩聲）
    collapsed.wav   被忽略 40 分鐘時播（內建版是往下的兩聲）

只放一個也可以，另一個會繼續用內建的。
刪掉檔案就回到內建，不需要改任何設定。

格式：WAV。mp3 或 m4a 改名成 .wav 不會生效，設定頁會顯示「不是 WAV 格式」。

音量由檔案本身決定，程式不會幫你調整——Windows 用系統音量播放，
程式在播的時候沒有辦法調小。內建那兩個的尖峰壓在滿刻度的 26%，
自己做的話可以拿它當基準。

內建的音檔在程式資料夾的 _internal\\assets\\sound\\ 底下，
可以複製出來當範本。

設定頁那兩列各有一顆「試聽」，換完可以立刻聽。
"""


def install(name, src):
    """把使用者選的檔案複製一份過來。回傳有沒有成功。

    先驗格式再複製。驗不過就什麼都不做——**留著上一次的設定，
    比覆蓋成一個播不出來的檔案好**：後者會讓一個原本正常的音效無聲地消失。
    """
    if not _is_wav(src):
        return False
    try:
        ensure_user_dir()
        shutil.copyfile(src, user_path(name))
        return True
    except OSError:
        return False


def remove(name):
    """回到內建。只刪我們複製過來的那一份，使用者的原檔不會被碰到。"""
    try:
        os.remove(user_path(name))
        return True
    except OSError:
        return False


def ensure_user_dir():
    """建好自訂資料夾，並放一份說明。回傳資料夾路徑。

    說明只在不存在時寫，不覆蓋——使用者可能在裡面加了自己的筆記。
    """
    os.makedirs(USER_DIR, exist_ok=True)
    readme = os.path.join(USER_DIR, README_NAME)
    if not os.path.exists(readme):
        with open(readme, "w", encoding="utf-8") as f:
            f.write(README_TEXT)
    return USER_DIR


def play(name):
    """播一個音。不阻塞，不拋例外，回傳有沒有真的送出去。"""
    ws = _backend()
    if ws is None:
        return False
    p = path(name)
    # 先自己確認檔案在。SND_NODEFAULT 已經擋掉「找不到檔案就播系統預設音」，
    # 但那個旗標是給 PlaySound 用的，先檢查一次可以連例外都不必進來。
    if not os.path.exists(p):
        return False
    try:
        # SND_ASYNC   立刻回來。同步播放會把 tick 卡住將近一秒。
        # SND_NODEFAULT 播不出來就安靜。**沒有這個旗標，失敗時 Windows 會播
        #             系統預設音**——那個聲音又大又不是我們的，比沒聲音糟得多。
        ws.PlaySound(p, ws.SND_FILENAME | ws.SND_ASYNC | ws.SND_NODEFAULT)
        return True
    except Exception:
        # 什麼都吞掉。理由見模組開頭：聲音壞掉不該影響提醒。
        return False

# -*- coding: utf-8 -*-
"""崩潰紀錄 —— `%LOCALAPPDATA%\\Sipbar\\crash.log`

## 為什麼需要

`run.bat` 走 `pythonw`，打包成 exe 之後也沒有 console。所以 traceback 印到
stderr 等於印到黑洞：**程式消失了，畫面上什麼都沒有，事後也查不到任何東西。**

使用者能回報的只有「它不見了」，而那句話修不了任何 bug。這個檔案存在的唯一
理由，就是把那句話換成一段可以讀的 traceback。

## 兩條進來的路

一、`sys.excepthook` —— 主執行緒沒被接住的例外。

二、Qt 的 slot。`settings.py` 的 `real_write_violations()` 記過這件事：
**Qt 會吞掉 slot 裡拋出的例外**，把 traceback 印到 stderr 然後讓程式繼續跑。
PySide6 的版本之間對這件事的處理不完全一樣（有的版本會轉給 `sys.excepthook`、
有的直接印掉），所以這裡兩條都掛：`sys.excepthook` 之外，`_hook_qt_slots()`
另外包一層。**寧可同一筆寫兩次，也不要有一整類崩潰完全沒有紀錄。**

## 三條硬規矩

**一、寫紀錄本身絕對不能再拋例外。** 它跑在程式已經出事的時候，這時候再炸一次
就什麼都不剩了。所有東西包在 try/except 裡，失敗就安靜放棄。

**二、不自動送出。** 檔案留在本機，使用者自己決定要不要貼給你。
`USAGE.md` 寫著「資料不出這台電腦」，這裡不能開後門。

**三、檔案要有上限。** 一個每天開機自啟的常駐程式，如果進了會反覆崩潰的迴圈，
無上限的 log 會在使用者不知情的狀況下長到幾百 MB。超過就砍掉最舊的。
"""
import os
import sys
import traceback
from datetime import datetime

import settings

MAX_BYTES = 64 * 1024           # 大約 100 筆。夠查最近幾次，又不會失控
KEEP_BYTES = 32 * 1024          # 超過上限時保留最後這麼多


def path():
    """每次都重算，不要在 import 時就凍住。

    測試會把 `settings.DATA_DIR` 換成沙箱，凍住的話就會寫進真實資料夾。
    """
    return os.path.join(settings.DATA_DIR, "crash.log")


def record(exc_type, exc, tb, source="excepthook"):
    """把一次崩潰寫進去。無論如何都不會拋例外。"""
    try:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        entry = (
            f"\n{'=' * 68}\n"
            f"{datetime.now().isoformat(timespec='seconds')}  "
            f"{settings.VERSION}  ({source})\n"
            f"{'=' * 68}\n{text}"
        )
        p = path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(entry)
        _trim(p)
    except Exception:                                   # noqa: BLE001
        # 寫紀錄的程式炸掉就安靜放棄。這時候程式已經在出事了，
        # 再拋一次只會把原本的 traceback 蓋掉。
        pass


def _trim(p):
    """超過上限就砍掉最舊的，從一整行的開頭切，不要切在半行。"""
    try:
        if os.path.getsize(p) <= MAX_BYTES:
            return
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            f.seek(os.path.getsize(p) - KEEP_BYTES)
            f.readline()                                # 丟掉被切一半的那行
            rest = f.read()
        with open(p, "w", encoding="utf-8") as f:
            f.write("（較舊的紀錄已因檔案大小上限被清除）\n" + rest)
    except OSError:
        pass


def install():
    """掛上兩條攔截路徑。由 island.main() 呼叫一次。"""
    prev = sys.excepthook

    def hook(exc_type, exc, tb):
        record(exc_type, exc, tb, "excepthook")
        prev(exc_type, exc, tb)                         # stderr 那份留著，
        #                                                 從 console 跑的時候還是看得到

    sys.excepthook = hook
    _hook_qt_slots()


def _hook_qt_slots():
    """PySide6 有些版本會把 slot 裡的例外吞掉，不轉給 sys.excepthook。

    有這支 API 就用，沒有就算了——它只是補一層，不是主要的路徑。
    """
    try:
        from PySide6.QtCore import qInstallMessageHandler, QtMsgType
    except ImportError:
        return

    def handler(mode, ctx, msg):
        # Qt 自己的致命訊息也值得留一筆。一般的 debug/info 不記，
        # 那些每秒好幾筆，會把真正的崩潰淹掉。
        if mode in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            try:
                p = path()
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "a", encoding="utf-8") as f:
                    f.write(f"\n{datetime.now().isoformat(timespec='seconds')}  "
                            f"{settings.VERSION}  (qt)\n{msg}\n")
                _trim(p)
            except Exception:                           # noqa: BLE001
                pass
        sys.__stderr__ and print(msg, file=sys.__stderr__)

    try:
        qInstallMessageHandler(handler)
    except Exception:                                   # noqa: BLE001
        pass


# 下面兩支是給設定頁的診斷區塊用的。它們跟 record() 適用同一條規矩：
# **絕對不能拋例外。** 接的是 Exception 不是 OSError——壞掉的路徑丟的可能是
# ValueError（例如含 null 字元）而不是 OSError，只接 OSError 的話，
# 一個讀不到的檔案會讓整個設定頁開不起來。診斷工具弄壞主程式是本末倒置。


def summary():
    """有沒有崩潰過、幾筆、最後一次是什麼時候。"""
    p = path()
    try:
        if not os.path.exists(p):
            return "無"
        size = os.path.getsize(p)
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = [ln for ln in f if ln.strip()]
        stamps = [ln.split()[0] for ln in lines
                  if ln[:4].isdigit() and "T" in ln[:20]]
        if not stamps:
            return f"有紀錄（{size} bytes）"
        return f"{len(stamps)} 筆，最後一次 {stamps[-1]}"
    except Exception:                                   # noqa: BLE001
        return "讀取失敗"


def tail(n=60):
    """最後 n 行。給「複製診斷資訊」用，不是給程式解析的。"""
    try:
        with open(path(), "r", encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-n:])
    except Exception:                                   # noqa: BLE001
        return ""

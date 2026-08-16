# -*- coding: utf-8 -*-
"""驗證 crashlog.py：寫得下、有上限、自己不會炸、excepthook 真的接得到。"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.stdout.reconfigure(errors="replace")

import settings as ap  # noqa: E402

# 沙箱要在任何測試之前。crashlog.path() 讀的是 settings.DATA_DIR，
# 沒導開的話這支測試會往使用者真實的資料夾裡塞假的崩潰紀錄。
SANDBOX = tempfile.mkdtemp(prefix="wp_crash_")
ap.DATA_DIR = os.path.join(SANDBOX, "data")
os.makedirs(ap.DATA_DIR, exist_ok=True)

import crashlog  # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + f"{label}: {got}"
          + ("" if ok else f"（預期 {want}）"))
    if not ok:
        fails.append(label)


def boom(depth=0):
    if depth < 2:
        return boom(depth + 1)
    raise ValueError("測試用的假崩潰")


def catch():
    try:
        boom()
    except ValueError:
        return sys.exc_info()
    return None


print("\n1. 路徑跟著 settings.DATA_DIR 走")
check("寫在沙箱裡", crashlog.path().startswith(SANDBOX), True)
check("還沒崩潰過時 summary 是「無」", crashlog.summary(), "無")

print("\n2. 記得下來，而且內容查得出東西")
crashlog.record(*catch())
text = open(crashlog.path(), encoding="utf-8").read()
check("檔案建出來了", os.path.exists(crashlog.path()), True)
check("有 traceback", "ValueError: 測試用的假崩潰" in text, True)
check("有出事的那一行", "boom" in text, True)
check("有版本號（回報時要對版本）", ap.VERSION in text, True)
check("summary 數得出來", crashlog.summary().startswith("1 筆"), True)

print("\n3. 檔案要有上限，不能無聲長到幾百 MB")
for _ in range(400):
    crashlog.record(*catch())
size = os.path.getsize(crashlog.path())
check("沒有超過上限", size <= crashlog.MAX_BYTES, True)
check("但也不是被清空", size > crashlog.KEEP_BYTES // 2, True)
tail = open(crashlog.path(), encoding="utf-8").read()
check("最近的那幾筆還在", "ValueError: 測試用的假崩潰" in tail, True)
check("切在整行上，不是半行", tail.splitlines()[0].startswith("（較舊"), True)

print("\n4. 寫紀錄自己絕對不能再拋例外")
# 程式已經在出事了，這時候記錄器再炸一次就什麼都不剩。
real_dir = ap.DATA_DIR
ap.DATA_DIR = "\x00:\\不可能存在的路徑"          # 連 makedirs 都會失敗
raised = None
try:
    crashlog.record(*catch())
except Exception as e:                            # noqa: BLE001
    raised = repr(e)
check("路徑寫不進去也安靜收場", raised, None)
check("summary 也不會炸", isinstance(crashlog.summary(), str), True)
check("tail 也不會炸", isinstance(crashlog.tail(), str), True)
ap.DATA_DIR = real_dir

print("\n5. install() 之後 sys.excepthook 真的會落檔")
os.remove(crashlog.path())
before = sys.excepthook
crashlog.install()
check("換掉了 excepthook", sys.excepthook is not before, True)
sys.excepthook(*catch())                          # 模擬一次沒被接住的例外
check("落檔了", os.path.exists(crashlog.path()), True)
check("而且是這一筆", "測試用的假崩潰" in open(crashlog.path(), encoding="utf-8").read(), True)
sys.excepthook = before

print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 項失敗：{fails}"))
sys.exit(1 if fails else 0)

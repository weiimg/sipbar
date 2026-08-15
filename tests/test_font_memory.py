# -*- coding: utf-8 -*-
"""字體序列的記憶體代價。

這支存在的理由是一個真實的回歸：把字體從單一家族改成四個家族的 fallback 序列，
島畫出文字之後記憶體從 89MB 變成 612MB、handle 從 342 變成 1153。
Qt 為了決定每個字元由誰來畫，會把序列上每個字體的字符表整份載進來，
而中文字體動輒三萬個字符。

常駐的桌面工具吃 600MB 是會被解除安裝的等級，而且完全沒有錯誤訊息——
只有打開工作管理員才看得到。所以把它釘成一條測試線。

用子行程量：字體資料庫沒有辦法在同一個行程裡卸載重來。
"""
import os
import subprocess
import sys
import textwrap

APP = r"E:\Claude Project\Claude Inbox\喝水提醒桌寵"
sys.path.insert(0, APP)

LIMIT_MB = 200          # 正常約 90MB；破 200 就是有人又把中文字體加進序列了

CHILD = textwrap.dedent(r'''
    import ctypes, sys
    from ctypes import wintypes
    sys.path.insert(0, r"{app}")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    import typeface
    {tweak}
    import island as isl, settings
    app = QApplication(["app"])
    typeface.ensure_loaded()
    cfg = settings.load_config()
    cfg["daily_target_drinks"] = settings.effective_target(cfg)
    w = isl.Island(cfg)
    # 只有真的畫出文字才會摸到字體，所以要跑真的事件迴圈讓打招呼的動畫演完。
    # 光 spin processEvents 不夠：內容彈簧有 90ms 延遲，字根本還沒畫出來，
    # 量到的會是「兩組都很省」的假通過。
    QTimer.singleShot(800, w.greet)
    QTimer.singleShot(4000, app.quit)
    app.exec()

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    # restype/argtypes 一定要宣告。ctypes 預設把回傳值當 c_int，
    # 而 GetCurrentProcess() 回的是 (HANDLE)-1，在 64 位元下會被截成 32 位元，
    # 呼叫就靜默失敗——第一版就是這樣量到 0 MB 而不是任何錯誤。
    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

    c = PMC(); c.cb = ctypes.sizeof(c)
    ok = psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    assert ok, "GetProcessMemoryInfo failed"
    print(int(c.PagefileUsage / 1048576))
''')


def measure(label, tweak):
    src = CHILD.format(app=APP, tweak=tweak)
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True, cwd=APP, timeout=180)
    if out.returncode != 0:
        print(f"  FAIL  {label}：子行程失敗\n{out.stderr[-600:]}")
        return None
    return int(out.stdout.strip().splitlines()[-1])


fails = []
print("島畫出文字之後的私有記憶體")

normal = measure("正常（隨附字體）", "")
if normal is None:
    fails.append("正常")
else:
    ok = normal < LIMIT_MB
    print(f"  {'ok  ' if ok else 'FAIL'} 正常路徑：{normal} MB（上限 {LIMIT_MB}）")
    if not ok:
        fails.append("正常路徑超過上限")

# 對照組：把中文字體塞回序列，證明這條線量得到、不是空的斷言。
# 這組「應該」很肥——它示範的正是不能做的事。
heavy = measure("多掛一個中文字體", 'typeface.FALLBACKS = ("Noto Sans TC", "Microsoft JhengHei UI")\n'
                                    'typeface._state = None\n'
                                    '_orig = typeface.make\n'
                                    'def make(px, weight, tracking=0.0, family=None):\n'
                                    '    typeface._cache.clear()\n'
                                    '    from PySide6.QtGui import QFont\n'
                                    '    f = QFont(); f.setFamilies(list(typeface.FALLBACKS))\n'
                                    '    f.setPixelSize(px); f.setWeight(weight)\n'
                                    '    return f\n'
                                    'typeface.make = make')
if heavy is not None and normal is not None:
    detects = heavy > normal + 100
    print(f"  {'ok  ' if detects else 'FAIL'} 對照組（序列多一個中文字體）：{heavy} MB"
          f"　比正常多 {heavy - normal} MB")
    if not detects:
        print("       對照組沒有變肥 -> 這條測試線失效了，量到的東西不對")
        fails.append("對照組沒反應")

print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 項失敗：{fails}"))
sys.exit(1 if fails else 0)

# -*- coding: utf-8 -*-
"""量 onefile 與 onedir 的啟動時間，用來決定發哪一個。

## 為什麼要量這個

onefile 是單一 exe，看起來乾淨，但它每次啟動都要把整包解壓到 %TEMP% 再執行。
Sipbar 是開機自啟的常駐程式，那個代價使用者每天付一次。
「乾淨」跟「每天等三秒」哪個重要，要有數字才談得下去。

## 判準是「島存了第一筆狀態」

不是量到 process 出現就算，那只代表 exe 被載入了。
island 建好之後會立刻 _persist() 一次（啟動就落檔，免得第一分鐘內被關掉
什麼都沒存到），所以 state.json 的 mtime 變動就是「程式真的活起來了」。

跑之前要先關掉正在執行的 Sipbar，否則單一實例的 mutex 會把新的擋掉，
量到的會是「立刻結束」。

用法：python tools/time_launch.py
"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import settings  # noqa: E402

TARGETS = [
    ("onedir", os.path.join(ROOT, "dist", "onedir", "Sipbar", "Sipbar.exe")),
    ("onefile", os.path.join(ROOT, "dist", "onefile", "Sipbar.exe")),
]
TIMEOUT = 60.0


def running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Sipbar.exe", "/NH"],
                         capture_output=True, text=True).stdout
    return "Sipbar.exe" in out


def kill():
    subprocess.run(["taskkill", "/F", "/IM", "Sipbar.exe"],
                   capture_output=True, text=True)
    for _ in range(50):
        if not running():
            return
        time.sleep(0.1)


def measure(exe):
    before = os.path.getmtime(settings.STATE_PATH) if \
        os.path.exists(settings.STATE_PATH) else 0.0
    t0 = time.perf_counter()
    subprocess.Popen([exe], cwd=os.path.dirname(exe))
    while time.perf_counter() - t0 < TIMEOUT:
        if os.path.exists(settings.STATE_PATH) and \
                os.path.getmtime(settings.STATE_PATH) > before:
            return time.perf_counter() - t0
        time.sleep(0.02)
    return None


def main():
    if running():
        print("FAIL 已經有 Sipbar.exe 在跑，先關掉再量")
        return 1

    print("量的是「從啟動到島存下第一筆狀態」。冷啟動只有第一次算數，")
    print("後面幾次作業系統已經把檔案快取起來了，所以兩次都列出來。\n")
    print(f"{'':<10}{'第一次':>9}{'第二次':>9}")
    for label, exe in TARGETS:
        if not os.path.exists(exe):
            print(f"{label:<10}  找不到 {exe}")
            continue
        runs = []
        for _ in range(2):
            kill()
            time.sleep(0.5)
            runs.append(measure(exe))
            time.sleep(0.5)
        kill()
        cells = "".join(f"{r:>8.2f}s" if r else f"{'逾時':>9}" for r in runs)
        print(f"{label:<10}{cells}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

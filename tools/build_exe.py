# -*- coding: utf-8 -*-
"""打包成 Windows 執行檔。

兩種模式各建一次，因為要用實測數字決定發哪一個：

- onedir：一個資料夾（Sipbar.exe + _internal\\）。解壓即用，那就是「portable」。
- onefile：單一 exe。乾淨，但每次啟動都要把整包解到 %TEMP% 再跑。

Sipbar 是開機自啟的常駐程式，啟動時間會被使用者每天感覺到一次，
所以這裡量的不只是體積，還有第一次啟動要多久。

## 為什麼要帶版本資訊

沒有 --version-file 的 exe，右鍵內容看到的是一片空白：沒有名稱、沒有版本、
沒有作者。防毒的啟發式偵測也把「沒有版本資訊」當成可疑訊號之一。

版本號從 settings.py 讀，不在這裡另外寫一份。用正規表示式抓而不是 import，
是為了不讓建置腳本依賴 PySide6 之類的執行期套件。

用法：python tools/build_exe.py
"""
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
NAME = "Sipbar"

VERSION_TMPL = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({a}, {b}, {c}, 0), prodvers=({a}, {b}, {c}, 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040404B0', [
      StringStruct('CompanyName', 'weiimg'),
      StringStruct('FileDescription', 'Sipbar'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'Sipbar'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 weiimg. MIT License.'),
      StringStruct('OriginalFilename', 'Sipbar.exe'),
      StringStruct('ProductName', 'Sipbar'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [1028, 1200])])]
)
"""


def version():
    src = open(os.path.join(SRC, "settings.py"), encoding="utf-8").read()
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', src, re.M)
    if not m:
        raise SystemExit("settings.py 裡找不到 VERSION")
    v = m.group(1)
    nums = [int(x) for x in re.findall(r"\d+", v)[:3]]
    while len(nums) < 3:
        nums.append(0)
    return v, nums


def write_version_file(v, nums):
    os.makedirs(BUILD, exist_ok=True)
    path = os.path.join(BUILD, "version_info.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(VERSION_TMPL.format(a=nums[0], b=nums[1], c=nums[2], ver=v))
    return path


def build(onefile, verfile):
    out = os.path.join(DIST, "onefile" if onefile else "onedir")
    shutil.rmtree(out, ignore_errors=True)
    args = [
        sys.executable, "-m", "PyInstaller",
        os.path.join(SRC, "island.py"),
        "--name", NAME,
        "--noconfirm", "--clean",
        # 不留 console 視窗。這是常駐工具，跳一個黑窗出來就毀了
        "--windowed",
        "--icon", os.path.join(ROOT, "assets", "icon.ico"),
        # 模組彼此是平的 sibling import，要告訴 PyInstaller src/ 是根
        "--paths", SRC,
        # 收進去的資源。目的路徑要對得上 settings.resource_dir() 的組法
        "--add-data", "%s;assets/fonts" % os.path.join(ROOT, "assets", "fonts"),
        "--add-data", "%s;assets" % os.path.join(ROOT, "assets", "icon.ico"),
        "--version-file", verfile,
        "--distpath", out,
        "--workpath", os.path.join(BUILD, "onefile" if onefile else "onedir"),
        "--specpath", BUILD,
    ]
    args.append("--onefile" if onefile else "--onedir")

    t0 = time.perf_counter()
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
        raise SystemExit("FAIL PyInstaller 失敗（%s）" % ("onefile" if onefile else "onedir"))
    return out, time.perf_counter() - t0


def tree_size(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    return sum(os.path.getsize(os.path.join(r, f))
               for r, _, fs in os.walk(path) for f in fs)


def main():
    v, nums = version()
    verfile = write_version_file(v, nums)
    print(f"版本 {v}\n")

    for onefile in (False, True):
        label = "onefile" if onefile else "onedir"
        out, secs = build(onefile, verfile)
        exe = os.path.join(out, NAME + ".exe") if onefile else \
            os.path.join(out, NAME, NAME + ".exe")
        if not os.path.exists(exe):
            raise SystemExit(f"FAIL 產不出 {exe}")
        total = tree_size(out)
        print(f"{label:<9} {total / 1024 / 1024:>6.1f} MB   建置 {secs:>5.0f} 秒")
        print(f"          {exe}")
    print("\n啟動時間要另外量，見 tools/time_launch.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

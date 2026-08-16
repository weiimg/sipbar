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


READ_ME = """Sipbar {ver}
https://github.com/weiimg/sipbar

執行 Sipbar.exe 就可以了，不用安裝。

第一次執行會跳「Windows 已保護您的電腦」
--------------------------------------
那是 SmartScreen 對沒有簽章的程式一律會跳的警告，不是偵測到問題。
點「其他資訊」，再點「仍要執行」。

程式碼簽章憑證一年要價數百美金，這是個人的 side project，沒有買。
不放心的話原始碼全部公開，可以自己從原始碼跑。

它在哪
------
平常完全隱藏。時間到才從螢幕頂端滑下來。
把滑鼠移到螢幕上緣中央可以隨時叫它出來。
系統匣（工作列右下角的「^」）也有一顆藍色的杯子圖示。

你的資料在哪
------------
%LOCALAPPDATA%\\Sipbar\\
設定、紀錄都在那裡，不在這個資料夾裡，所以這包可以隨便搬。
不用了就把整個資料夾刪掉，再把上面那個目錄刪掉，什麼都不會留下。

授權
----
程式碼是 MIT，見 LICENSE。
隨附字體另依 SIL Open Font License 1.1 散布，
授權條文在 _internal\\assets\\fonts\\ 裡。
"""


def package(v):
    """把 onedir 的產物加上授權與說明，壓成發布用的 zip。

    LICENSE 一定要進去：MIT 要求散布時附上著作權聲明，而使用者拿到的是這包，
    不是版本庫。字體的 OFL 由 --add-data 收進 _internal 裡，同樣的理由。
    """
    import zipfile
    src = os.path.join(DIST, "onedir", NAME)
    if not os.path.isdir(src):
        raise SystemExit("FAIL 找不到 onedir 的產物")

    # README.txt 寫成 UTF-8 with BOM。內容是中文，而收到這包的人多半在
    # 繁中 Windows 上：沒有 BOM 的話，任何用系統預設編碼（cp950）打開的工具
    # 都會顯示成亂碼。看不懂的說明比沒有說明更糟，因為裡面寫的是
    # 「SmartScreen 會跳警告、那不是中毒」。
    #
    # LICENSE 全是 ASCII，不需要 BOM，而且授權條文照原樣不動比較保險。
    extra = [
        ("LICENSE", open(os.path.join(ROOT, "LICENSE"), encoding="utf-8").read(), "utf-8"),
        ("README.txt", READ_ME.format(ver=v), "utf-8-sig"),
    ]
    out = os.path.join(DIST, f"Sipbar-{v}-portable.zip")
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for r, _, fs in os.walk(src):
            for f in fs:
                p = os.path.join(r, f)
                z.write(p, os.path.join(NAME, os.path.relpath(p, src)))
        for name, text, enc in extra:
            z.writestr(os.path.join(NAME, name),
                       text.replace("\n", "\r\n").encode(enc))
    return out


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

    zip_path = package(v)
    print(f"\n發布用 {tree_size(zip_path) / 1024 / 1024:>6.1f} MB   {zip_path}")
    print("\n啟動時間要另外量，見 tools/time_launch.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

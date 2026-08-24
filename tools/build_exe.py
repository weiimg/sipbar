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
import stat
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


def sha256(path):
    """發布檔的雜湊。給 release 頁面貼，讓下載的人驗得了完整性。"""
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# PyInstaller 在 Windows 上會以 PermissionError: [WinError 5] 失敗。
# **同一個訊息有兩種完全不同的原因，而它們的解法相反。**
#
# 一、上一輪留下的資料夾帶著 ReadOnly 屬性（最常見的是 PyInstaller 自己建的
#     localpycs）。`os.rmdir()` 對唯讀資料夾一律回 WinError 5，看起來跟「被別的
#     程式佔著」一模一樣。這一種**重跑幾次都不會過**，因為每一輪都撞同一個殘留。
#     解法是刪之前先把屬性清掉，也就是底下的 _force_rmtree()。
#
# 二、真的有東西抓著 handle——Sipbar 還在跑（含從原始碼跑的），或防毒剛好在掃。
#     這一種等幾秒重試就過得去。
#
# 2026-08-24 花了四輪才分清楚：先照 RELEASE.md 的說法找有沒有 Sipbar 在跑
# （沒有），再猜防毒（加了重試，還是每次卡在同一個 localpycs），最後才看到
# 那個資料夾的屬性是 ReadOnly。**分辨方法**：PowerShell 的 `Remove-Item -Force`
# 刪得掉就是第一種（它會先清屬性），刪不掉才是第二種。
LOCK_ERROR = "WinError 5"
BUILD_TRIES = 3
LOCK_WAIT_S = 3.0


def _force_rmtree(path):
    """刪掉整棵目錄，包含帶 ReadOnly 屬性的。

    `shutil.rmtree(ignore_errors=True)` 在這裡是陷阱：它把唯讀那一種**安靜地
    跳過**，於是殘留留在原地，下一輪重試撞同一個地方，而畫面上看起來像
    「清過了還是失敗」。
    """
    if not os.path.isdir(path):
        return

    def clear(func, target, exc):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass        # 真的被佔著就留給 PyInstaller 去撞，它的訊息比較有用

    shutil.rmtree(path, onexc=clear)


def build(onefile, verfile):
    out = os.path.join(DIST, "onefile" if onefile else "onedir")
    work = os.path.join(BUILD, "onefile" if onefile else "onedir")
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
        "--add-data", "%s;assets/sound" % os.path.join(ROOT, "assets", "sound"),
        "--add-data", "%s;assets" % os.path.join(ROOT, "assets", "icon.ico"),
        "--version-file", verfile,
        "--distpath", out,
        "--workpath", work,
        "--specpath", BUILD,
    ]
    args.append("--onefile" if onefile else "--onedir")

    label = "onefile" if onefile else "onedir"
    t0 = time.perf_counter()
    for attempt in range(1, BUILD_TRIES + 1):
        # 兩個目錄都先清掉再跑，連唯讀的一起（見 _force_rmtree）。
        _force_rmtree(out)
        _force_rmtree(work)
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if r.returncode == 0:
            return out, time.perf_counter() - t0
        if LOCK_ERROR in (r.stdout + r.stderr) and attempt < BUILD_TRIES:
            print("  %s 撞到 WinError 5（第 %d 次），清掉殘留等 %.0f 秒再試"
                  % (label, attempt, LOCK_WAIT_S))
            time.sleep(LOCK_WAIT_S)
            continue
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
        if LOCK_ERROR in (r.stdout + r.stderr):
            print("  試了 %d 次都是 WinError 5。清屬性已經試過了，所以是真的有東西"
                  "抓著：先確認沒有 Sipbar 在跑（含從原始碼跑的），再看防毒。"
                  % BUILD_TRIES)
        raise SystemExit("FAIL PyInstaller 失敗（%s）" % label)


READ_ME = """Sipbar {ver}
https://github.com/weiimg/sipbar

執行 Sipbar.exe 就可以了，不用安裝。

第一次執行會跳「Windows 已保護您的電腦」
--------------------------------------
點「其他資訊」，再點「仍要執行」。
Windows 對所有沒有數位簽章的程式都會這樣。

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
    # SHA256 一起印出來，發版時貼進 release 頁面。
    #
    # exe 沒有數位簽章（憑證要年費），所以下載的人沒有任何辦法確認拿到的
    # 是不是原本那一份。雜湊擋不掉 SmartScreen 的警告，但至少驗得了完整性。
    # 要人「自己去算一個雜湊」不會有人做，發版時順手貼上去才會有人用。
    print(f"       SHA256 {sha256(zip_path)}")
    print("\n啟動時間要另外量，見 tools/time_launch.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

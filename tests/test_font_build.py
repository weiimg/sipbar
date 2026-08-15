# -*- coding: utf-8 -*-
"""隨程式散布的字體是合成品，這支負責證明它沒合壞。

## 為什麼需要這支

`tools/build_font.py` 把 Inter 的拉丁字形寫進 Noto Sans TC 的 CFF。這個過程有
好幾個**不會報錯的**失敗方式，而且從字體檔本身看起來都是對的：

- **寬度編碼**：T2 charstring 的寬度是相對 `nominalWidthX` 的。傳實際寬度進去，
  hmtx 仍然是對的、fontTools 讀得出來、檔案也開得起來——只有真的畫出來才會發現
  每個數字都寬了一倍。實測就是這樣過了一輪。
- **拿錯 Private**：Noto 是 CID-keyed，18 個 FontDict 各有一本，拿錯就是另一組偏移。
- **upem 沒對齊**：Inter 2048、Noto 1000，忘了縮就是兩倍大的字形。
- **直排度量被覆蓋**：hhea 一變，整個介面的行高就跟著變，版面全部要重排。

共通點是：**它們都不會讓程式壞掉，只會讓字看起來怪。** 所以量，不要看。

## 判準綁在來源字體上，不寫死數字

每個被換掉的字，寬度必須等於 Inter 的；每個沒換的字，必須等於 Noto 的。
寫死「數字是 648」的話，換一版 Inter 就變成假失敗。
"""
import os
import sys

APP = r"E:\Claude Project\Claude Inbox\喝水提醒桌寵"
sys.path.insert(0, APP)
sys.path.insert(0, os.path.join(APP, "tools"))

from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QFontMetricsF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from fontTools.ttLib import TTFont  # noqa: E402

import build_font  # noqa: E402
import typeface  # noqa: E402

app = QApplication(sys.argv)
fails = []


def check(label, got, want, tol=0):
    ok = abs(got - want) <= tol if isinstance(got, (int, float)) \
        and isinstance(want, (int, float)) else got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}: {got}" + ("" if ok else f"（預期 {want}）"))
    if not ok:
        fails.append(label)


print("1. Qt 真的拿得到這個字體")
ok, detail = typeface.ensure_loaded()
check("載入成功", ok, True)
print(f"       {detail}")
for px, weight, want_w in ((17, QFont.Medium, 500), (28, QFont.Bold, 700)):
    info = QFontInfo(typeface.make(px, weight))
    check(f"{px}px 解析到的家族", info.family(), typeface.FAMILY)
    check(f"{px}px 解析到的字重", info.weight(), want_w)

print("\n2. 中文一個都不能少，直排度量一格都不能變")
# 度量一變，整個介面的行高就跟著變——那不是字體問題，是版面全部要重排。
for out_name, src_name, _wght, _wc, style in build_font.WEIGHTS:
    built = TTFont(os.path.join(build_font.OUT, out_name))
    src = TTFont(os.path.join(build_font.SRC, src_name))
    check(f"{style} cmap 字數", len(built.getBestCmap()), len(src.getBestCmap()))
    check(f"{style} upem", built["head"].unitsPerEm, src["head"].unitsPerEm)
    for attr in ("ascent", "descent", "lineGap"):
        check(f"{style} hhea.{attr}", getattr(built["hhea"], attr),
              getattr(src["hhea"], attr))
    for attr in ("sTypoAscender", "sTypoDescender", "usWinAscent", "usWinDescent"):
        check(f"{style} OS/2.{attr}", getattr(built["OS/2"], attr),
              getattr(src["OS/2"], attr))

print("\n3. 換掉的字要是 Inter 的寬度，沒換的要維持 Noto 的")
# **用 Qt 量，不要只讀 hmtx。** 寬度編碼那個 bug 的 hmtx 完全正確，
# 錯的是 CFF charstring 裡的值，而畫出來的是後者。
PX = 100                        # 量大一點，四捨五入的誤差才不會蓋掉真正的差
qf = QFont()
qf.setFamilies([typeface.FAMILY])
qf.setPixelSize(PX)
qf.setWeight(QFont.Medium)
qm = QFontMetricsF(qf)

src = TTFont(os.path.join(build_font.SRC, build_font.WEIGHTS[0][1]))
inter = build_font.latin_source(build_font.WEIGHTS[0][2])
tnum = build_font.tabular_names(inter)
i_cmap, n_cmap = inter.getBestCmap(), src.getBestCmap()
upem = src["head"].unitsPerEm


def em(font, cmap, cp, tabular=False):
    name = cmap[cp]
    if tabular:
        name = tnum.get(name, name)
    return font["hmtx"][name][0] / upem * PX


wrong_latin = []
for cp in build_font.SUBSTITUTE:
    if cp not in i_cmap or cp not in n_cmap:
        continue
    want = em(inter, i_cmap, cp, cp in build_font.TABULAR)
    got = qm.horizontalAdvance(chr(cp))
    if abs(got - want) > 1.0:
        wrong_latin.append(f"U+{cp:04X} {chr(cp)!r} 畫成 {got:.1f} 應是 {want:.1f}")
check(f"{len(build_font.SUBSTITUTE)} 個換掉的字寬度都等於 Inter",
      wrong_latin[:4] or "全對", "全對")

# 空白、間隔號、中文刻意不換。它們出現在中文行裡，該用中文字體的版本。
KEEP = [0x20, 0x00B7, ord("中"), ord("水"), ord("續"), 0x3001, 0xFF0C]
wrong_cjk = []
for cp in KEEP:
    if cp not in n_cmap:
        continue
    want = em(src, n_cmap, cp)
    got = qm.horizontalAdvance(chr(cp))
    if abs(got - want) > 1.0:
        wrong_cjk.append(f"U+{cp:04X} {chr(cp)!r} 畫成 {got:.1f} 應是 {want:.1f}")
check("空白／間隔號／中文維持 Noto 的寬度", wrong_cjk or "全對", "全對")

print("\n4. 數字必須等寬")
# 這個介面的數字全都會變（連續天數數上來、今天 3/7 次、08:00、還剩 109 分）。
# 比例寬會讓數字一變、旁邊的東西就跟著左右跳。
widths = {round(qm.horizontalAdvance(d), 2) for d in "0123456789"}
check("十個數字同寬", sorted(widths), [sorted(widths)[0]])

print("\n5. 介面上真的會出現的字，一個都不能是豆腐")
# 字體沒有子集化，理論上不會缺字；但如果哪天為了瘦身而子集化，
# 這條就是唯一擋得下「某個字沒被收進去」的線。
covered = set(TTFont(os.path.join(build_font.OUT,
                                  build_font.WEIGHTS[0][0])).getBestCmap())
missing = set()
for name in ("island.py", "stats_window.py", "menu.py", "onboard.py", "settings.py"):
    for ch in open(os.path.join(APP, name), encoding="utf-8").read():
        if ord(ch) > 0x2000 and ord(ch) not in covered:
            missing.add(ch)
check("原始碼裡出現過的字都畫得出來", "".join(sorted(missing))[:20] or "全有", "全有")

print("\n6. 每個換過的字形，畫出來要跟 Inter 畫出來的一樣")
# 寬度對、度量對，字形本身仍然可能在 qu2cu 轉曲線時走樣。
#
# **這一條不能用眼睛驗。** 第一版的字樣圖把 64px 的點陣圖用最近鄰放大兩倍，
# 於是「1」缺一角、「4」被劃一刀、beta 的 t 破掉——看起來像字形轉壞了，
# 實際上字體完全正常，壞的是那張圖。差點就照著這個假象去改建置腳本。
# 所以改成把兩邊各畫一次、逐像素比，機器說了算。
#
# **要在夠大的尺寸比。** 一開始在 64px 比，得到 # 差 14.9%、+ 差 10.8%，
# 看起來像轉壞了；但同樣的字在 256px 是逐像素完全一致（0.0%）。
# 那個差來自格線對齊：CFF 與 glyf 兩套驅動的 grid-fitting 不一樣，
# 而且 Qt 在 Windows 上不理會 PreferNoHinting。**小尺寸量到的是柵格化的雜訊，
# 不是字形的差別**，而這一節要驗的是後者。
import io as _io  # noqa: E402

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402

buf = _io.BytesIO()
inter.save(buf)
inter_id = QFontDatabase.addApplicationFontFromData(buf.getvalue())
INTER_FAMILY = QFontDatabase.applicationFontFamilies(inter_id)[0]

# 名字不能叫 PX：第 3 節的 em() 會讀那個全域來換算 hmtx，被蓋掉之後
# 第 7 節拿 256 的期望值去比 100px 量到的寬度，三個沒換的字元全部誤報成被換掉。
RASTER_PX = 256                 # 小於這個就開始量到柵格化的雜訊，見上面
CELL = RASTER_PX * 2


def raster(family, ch, tabular_feature):
    f = QFont()
    f.setFamilies([family])
    f.setPixelSize(RASTER_PX)
    f.setWeight(QFont.Medium)
    if tabular_feature:
        # 成品的數字直接就是等寬那一組；要跟它比，Inter 這邊得把 tnum 打開。
        f.setFeature(QFont.Tag("tnum"), 1)
    img = QImage(CELL, CELL, QImage.Format_Grayscale8)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.TextAntialiasing, True)
    p.setFont(f)
    p.setPen(QColor(255, 255, 255))
    p.drawText(QPoint(RASTER_PX // 6, int(RASTER_PX * 1.2)), ch)
    p.end()
    return img


def diff(a, b):
    """回傳「差超過門檻的像素」占有墨像素的比例。"""
    ink = bad = 0
    for y in range(CELL):
        for x in range(CELL):
            va = a.pixelColor(x, y).red()
            vb = b.pixelColor(x, y).red()
            if va > 8 or vb > 8:
                ink += 1
                if abs(va - vb) > 72:
                    bad += 1
    return bad / ink if ink else 0.0


worst = ("", 0.0)
broken = []
for cp in build_font.SUBSTITUTE:
    if cp not in i_cmap or cp not in n_cmap:
        continue
    ch = chr(cp)
    tab = cp in build_font.TABULAR
    ratio = diff(raster(typeface.FAMILY, ch, tab), raster(INTER_FAMILY, ch, tab))
    if ratio > worst[1]:
        worst = (ch, ratio)
    if ratio > 0.01:
        broken.append(f"{ch!r} 差 {ratio:.1%}")
check("轉出來的字形跟 Inter 一致", broken[:5] or "全對", "全對")
print(f"       差最多的是 {worst[0]!r}，{worst[1]:.2%} 的像素不同（門檻 1%）")

print("\n7. 介面用到的每個非中文字元，都要判斷過要不要換")
# **這一節是修 bug 修出來的。** 初版用「Latin-1 補充區用不到」這個猜測排除整個區塊，
# 結果「3440×1440」變成兩個 Inter 數字夾一個 Noto 乘號——大一號、重一號、
# 左右還帶著中文字體的留白。判準不是碼位落在哪個區塊，是它出現在什麼字之間。
#
# 所以這裡不檢查「換得對不對」（那是設計判斷），只檢查**有沒有判斷過**：
# 每個字元要嘛在 SUBSTITUTE、要嘛在 KEEP_NOTO 並附理由。漏掉就擋下來。
import io as _io2  # noqa: E402
import re as _re  # noqa: E402

STRING = _re.compile('"([^"]*)"')


def is_cjk(ch):
    cp = ord(ch)
    return 0x3000 <= cp <= 0x9FFF or 0xFF00 <= cp <= 0xFFEF


undecided = {}
for name in ("island.py", "stats_window.py", "menu.py", "onboard.py", "settings.py"):
    for lineno, line in enumerate(_io2.open(os.path.join(APP, name),
                                            encoding="utf-8"), 1):
        if line.lstrip().startswith("#"):
            continue
        for m in STRING.finditer(line):
            for ch in m.group(1):
                cp = ord(ch)
                if ch.isascii() or is_cjk(ch):
                    continue
                if cp in build_font.SUBSTITUTE or cp in build_font.KEEP_NOTO:
                    continue
                undecided.setdefault(f"U+{cp:04X} {ch!r}", f"{name}:{lineno}")
check("沒有未判斷的字元",
      [f"{k}（{v}）" for k, v in undecided.items()] or "全部判斷過", "全部判斷過")
if undecided:
    print("       把它加進 build_font.SUBSTITUTE（夾在拉丁字之間）"
          "或 KEEP_NOTO（前後是中文，要附理由）")

# 不換的那些，字形必須真的還是 Noto 的
wrong_keep = []
for cp in build_font.KEEP_NOTO:
    if cp not in n_cmap:
        continue
    want = em(src, n_cmap, cp)
    got = qm.horizontalAdvance(chr(cp))
    if abs(got - want) > 1.0:
        wrong_keep.append(f"U+{cp:04X} {chr(cp)!r} 被換掉了")
check("KEEP_NOTO 裡的字元確實沒被換到", wrong_keep or "全對", "全對")

print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 項失敗"))
sys.exit(1 if fails else 0)

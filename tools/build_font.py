# -*- coding: utf-8 -*-
r"""把 Inter 的拉丁字形合進 Noto Sans TC，產生隨程式散布的單一字體。

## 為什麼一定要合成一個檔

**只要 Qt 需要為任何一個字做字體回退，它就會把一整份中文字符表載進記憶體。**

實測（tests/test_font_memory.py 的量法，島畫出文字之後的私有記憶體）：

| 做法 | 記憶體 |
|---|---|
| 只掛 Noto Sans TC（單一家族，自己蓋得住全部的字） | 56 MB |
| `setFamilies(["Inter", "Noto Sans TC"])` | 396 MB |
| 只掛 Inter，中文交給系統回退 | 394 MB |
| 兩個獨立字體，各自只畫自己蓋得到的字 | 56 MB |

貴的不是 Inter（2,849 個字符），是**被迫整份載入的 Noto**（20,745 個）。
所以 CSS 那種 `font-family: Inter, "Noto Sans TC"` 的寫法在這裡直接封死：
一個常駐的桌面工具吃 400MB 是會被解除安裝的等級。

「兩個獨立字體」那條路成本是零，但會讓同一張卡裡出現兩種數字設計
（「08:00」是 Inter、正上方的「23:00 起改為每 109 分」是 Noto），
那看起來像 bug 不像設計。所以走這裡：**離線合成，出貨單一家族。**

## 為什麼是換字形，不是 fontTools.merge

Noto 是 CFF（PostScript 曲線），Inter 是 glyf（TrueType 曲線），`merge` 不吃混的。
要合就得先轉一邊：

- 把 Noto 的 20,950 個字轉成 glyf——CFF 對中文緊湊得多，轉完檔案會膨脹好幾 MB
- 把 Inter 的 2,933 個字轉成 CFF——只動小的那邊

而且我們要的本來就不是「合併兩個字體」，是「把 Noto 的拉丁字換成 Inter 的」。
所以做法是：把 Inter 的字形轉成 T2 charstring，蓋掉 Noto 裡對應的那幾個，
其餘一律不動。Noto 的直排度量、CJK 字形、cmap 全部原封不動，檔案大小幾乎不變。

## 刻意不換的東西

- **U+0020 空白**：它在「今天 3/7 次」這種句子裡是中英之間的間隔，
  Noto 的空白是配著中文調的，換成拉丁度量的會讓中英夾雜的行擠在一起。
- **U+00B7 間隔號**：島上的「連續 5 天 · 下次約 30 分後」用它當分隔，
  兩邊都是中文，那個位置該用中文字體的版本。
- **Latin-1 補充區以上**：用不到，換了只是多出沒驗證過的字形。

原則是：**出現在拉丁字串裡的才換，出現在中文行裡的維持 Noto。**

## 授權

兩份都是 SIL OFL 1.1，而且**都沒有宣告 Reserved Font Name**（授權檔的著作權行
沒有「with Reserved Font Name」），所以衍生字體可以散布。但仍然改名：
成品既不是 Inter 也不是 Noto Sans TC，掛著任一個原名都是在誤導。

OFL 要求衍生物同樣用 OFL 散布並附上授權，見 assets/fonts/README.md。

## 用法

    python tools/build_font.py

來源放 tools/fontsrc/（跟著版本庫走，理由見該資料夾的 README），
成品寫進 assets/fonts/。需要 `pip install fonttools`，只有建置需要。

**改完一定要跑 `tests/test_font_build.py`。** 這裡每一種失敗方式都是靜默的：
字體開得起來、程式跑得動、只有畫出來才看得出不對。
"""

import os
import sys

from fontTools.misc.psCharStrings import T2WidthExtractor
from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import scale_upem
from fontTools.varLib import instancer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "fontsrc")
OUT = os.path.join(ROOT, "assets", "fonts")

INTER = os.path.join(SRC, "Inter[opsz,wght].ttf")
FAMILY = "WaterPet Sans TC"
POSTSCRIPT = "WaterPetSansTC"

# Inter 的 opsz 軸是 14–32。介面的字級是 15–28px，只有連續天數那個大數字是 64px，
# 所以釘在小字那一端：14 的字腔開、字距鬆，那是為小字設計的那一版。
OPSZ = 14.0

WEIGHTS = (
    # (輸出檔名, Noto 來源, Inter 的 wght, OS/2 usWeightClass, 樣式名)
    ("WaterPetSansTC-Medium.otf", "NotoSansTC-Medium.otf", 500, 500, "Medium"),
    ("WaterPetSansTC-Bold.otf", "NotoSansTC-Bold.otf", 700, 700, "Bold"),
)

# 要換掉的碼位。ASCII 可見字元（不含空白）＋ 幾個排版用的標點。
# 為什麼不多給一點：每多一個碼位就多一個沒人看過的字形，而這些字最後是靠
# tests/render_font.py 用眼睛驗的，驗不完的就不要放進來。
SUBSTITUTE = (
    list(range(0x21, 0x7F))              # ! .. ~ ：數字、大小寫、ASCII 標點
    + [0x2013, 0x2014,                   # – —
       0x2018, 0x2019, 0x201C, 0x201D,   # ' ' " "
       0x2026]                           # …
)

# 數字要等寬。Inter 預設的數字是比例寬（`1` 是 415、`0` 是 646），
# 那對內文是對的，對介面是錯的：這個介面的數字全都會變
# （連續天數從 0 數上來、今天 3/7 次、08:00、還剩 109 分），
# 比例寬會讓數字一變、旁邊的東西就跟著左右跳。Noto 原本的數字全部是 570，
# 換過去等於把這個性質弄丟。
#
# Inter 有等寬數字，掛在 tnum 這個 OpenType 特性底下，是另一組字形（.tf 結尾、
# 全部 648 寬）。**直接取那一組，不要在執行期開 tnum**——字體裡就只有一種數字，
# 呼叫端不會有機會忘記開。
TABULAR = set(range(0x30, 0x3A))

COPYRIGHT = ("Latin glyphs from Inter, Copyright 2020 The Inter Project Authors. "
             "CJK and all other glyphs from Noto Sans TC, Copyright 2014-2021 Adobe. "
             "Both licensed under the SIL Open Font License 1.1.")
LICENSE = ("This Font Software is licensed under the SIL Open Font License, "
           "Version 1.1. This license is available with a FAQ at "
           "https://scripts.sil.org/OFL")
LICENSE_URL = "https://scripts.sil.org/OFL"


def latin_source(wght):
    """把可變的 Inter 定成一個字重的靜態字體，並縮到 Noto 的 upem。

    upem 一定要先對齊（Inter 2048、Noto 1000），否則字形貼進去會是原來的兩倍大。
    scale_upem 會連 hmtx 一起換算，所以要在讀寬度之前做。
    """
    font = instancer.instantiateVariableFont(
        TTFont(INTER), {"wght": wght, "opsz": OPSZ}, inplace=False)
    scale_upem(font, 1000)
    return font


def tabular_names(inter):
    """從 GSUB 讀出 tnum 的替換表：比例寬字形名 -> 等寬字形名。

    不寫死 "zero" -> "zero.tf"：命名是 Inter 自己的慣例，不是規格，
    換一版字體就可能改。問字體本身，答案才會跟著字體走。
    """
    mapping = {}
    for record in inter["GSUB"].table.FeatureList.FeatureRecord:
        if record.FeatureTag != "tnum":
            continue
        for index in record.Feature.LookupListIndex:
            for sub in inter["GSUB"].table.LookupList.Lookup[index].SubTable:
                mapping.update(getattr(sub, "mapping", {}))
    return mapping


def rename(font, style, weight_class):
    """改名。成品既不是 Inter 也不是 Noto Sans TC，掛原名是誤導。

    name 表與 CFF 的 topDict 兩邊都要改——只改 name 表的話，
    有些系統會從 CFF 讀 FontName，兩邊對不起來。
    """
    full = f"{FAMILY} {style}"
    ps = f"{POSTSCRIPT}-{style}"
    # ID1/ID2 是舊式的四風格分組，ID16/ID17 是排版家族。兩組都寫，
    # Windows 才會把 Medium 與 Bold 收在同一個家族底下。
    records = {
        0: COPYRIGHT, 1: FAMILY if style == "Bold" else full,
        2: "Bold" if style == "Bold" else "Regular",
        3: f"{ps}; WaterPet build", 4: full, 6: ps,
        13: LICENSE, 14: LICENSE_URL, 16: FAMILY, 17: style,
    }
    name = font["name"]
    name.names = [r for r in name.names if r.nameID not in records]
    for nid, value in records.items():
        name.setName(value, nid, 3, 1, 0x409)      # Windows / Unicode BMP / en-US
        name.setName(value, nid, 1, 0, 0)          # Mac / Roman / English

    top = font["CFF "].cff.topDictIndex[0]
    font["CFF "].cff.fontNames = [ps]
    top.FullName, top.FamilyName, top.Weight = full, FAMILY, style

    font["OS/2"].usWeightClass = weight_class


def substitute(noto, inter, codepoints):
    """把 Inter 的字形寫進 Noto 的 CFF，並換掉對應的寬度。

    寬度一定要一起換。只換字形不換 hmtx 的話，Inter 比較窄的數字會被塞進
    Noto 的寬度裡，字與字之間出現一格一格的空隙，看起來像沒對齊。
    """
    n_cmap, i_cmap = noto.getBestCmap(), inter.getBestCmap()
    i_glyphs = inter.getGlyphSet()
    tnum = tabular_names(inter)
    cff = noto["CFF "].cff
    top = cff.topDictIndex[0]
    charstrings = top.CharStrings
    global_subrs = cff.GlobalSubrs
    hmtx = noto["hmtx"]

    done, skipped = [], []
    for cp in codepoints:
        n_name, i_name = n_cmap.get(cp), i_cmap.get(cp)
        if not n_name or not i_name:
            skipped.append(cp)
            continue
        if cp in TABULAR:
            i_name = tnum.get(i_name, i_name)
        # **Noto Sans TC 是 CID-keyed CFF**：字形叫 cid00017 不叫 zero，而且
        # 18 個 FontDict 各有自己的 Private（這一族的 nominalWidthX 是 651）。
        # T2 charstring 的寬度是相對 nominalWidthX 編碼的，拿錯一本 Private
        # 產出來的字寬度會整個偏掉，而且不會有任何錯誤。
        _old, fd_index = charstrings.getItemAndSelector(n_name)
        private = top.FDArray[fd_index].Private

        width = int(round(i_glyphs[i_name].width))
        # **T2 charstring 的寬度是相對 nominalWidthX 編碼的，而 T2CharStringPen
        # 直接把你給的數字原封塞進去。** 傳實際寬度的話，解出來會是
        # `nominalWidthX + 你給的值`——648 的數字變成 1299，畫出來剛好兩倍寬。
        # 而且 hmtx 是對的，所以從 hmtx 檢查完全看不出問題（實測就是這樣過了一輪，
        # 直到 test_island 的 17b 用字體度量量出「連續 128 天…」多了 72px）。
        #
        # 等於 defaultWidthX 時要整個省略，那是 CFF 的預設值機制。
        pen_width = None if width == private.defaultWidthX \
            else width - private.nominalWidthX
        pen = T2CharStringPen(pen_width, i_glyphs)
        # 兩層轉換，順序是由內往外包：
        #
        # 1. **輪廓方向反過來。** TrueType 的外輪廓是順時針，PostScript 是逆時針。
        #    非零環繞規則下只要內外相對方向一致就填得對，所以不反也畫得出來
        #    （實測兩種版本在螢幕上看不出差別）。反過來是因為那是 CFF 的慣例，
        #    字體檢查工具與部分 hinting 引擎會據此判斷，不是為了修某個看得到的 bug。
        # 2. Inter 是二次曲線、CFF 只吃三次曲線。all_cubic 讓轉出來的全是曲線段，
        #    不留二次曲線轉成的直線近似。
        i_glyphs[i_name].draw(
            Qu2CuPen(ReverseContourPen(pen), max_err=0.5, all_cubic=True))
        cs = pen.getCharString(private=private)
        cs.private = private
        # 讀回來確認。這條路上兩個地方會靜默給出錯的寬度（相對編碼、預設值省略），
        # 兩個都不會報錯，只會讓字距整個跑掉。用真的解碼器讀，不要自己算一次——
        # 自己算等於把同一個假設寫兩遍，錯了也一起錯。
        extractor = T2WidthExtractor(getattr(private, "Subrs", []) or [],
                                     global_subrs, private.nominalWidthX,
                                     private.defaultWidthX)
        extractor.execute(cs)
        if extractor.width != width:
            raise SystemExit(f"U+{cp:04X} 寬度編碼錯了："
                             f"寫進去 {width}，讀回來 {extractor.width}")
        charstrings[n_name] = cs
        # lsb 從實際輪廓算，不要沿用 Noto 的：兩套字形的左側留白不一樣。
        bounds = cs.calcBounds(charstrings)
        hmtx[n_name] = (width, int(round(bounds[0])) if bounds else 0)
        done.append(cp)
    return done, skipped


def build():
    os.makedirs(OUT, exist_ok=True)
    missing = [p for p in (INTER,) + tuple(
        os.path.join(SRC, src) for _o, src, *_r in WEIGHTS) if not os.path.exists(p)]
    if missing:
        raise SystemExit("缺少來源字體：\n  " + "\n  ".join(missing)
                         + "\n見 tools/fontsrc/README.md")

    for out_name, noto_name, wght, weight_class, style in WEIGHTS:
        noto = TTFont(os.path.join(SRC, noto_name))
        inter = latin_source(wght)

        done, skipped = substitute(noto, inter, SUBSTITUTE)
        rename(noto, style, weight_class)

        path = os.path.join(OUT, out_name)
        noto.save(path)
        size = os.path.getsize(path) / 1048576
        print(f"  {out_name}：換掉 {len(done)} 個字形"
              f"{f'（跳過 {len(skipped)} 個兩邊沒有的）' if skipped else ''}"
              f"　{size:.1f} MB")


if __name__ == "__main__":
    print(f"合成 {FAMILY}（Inter 的拉丁 + Noto Sans TC 的中文）")
    build()
    print("完成。記得跑 tests/test_font_build.py")

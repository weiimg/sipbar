# -*- coding: utf-8 -*-
"""介面文案的風格檢查。

## 兩種文案，兩套標準

**島的訊息**（`island.MESSAGES`：「口渴了」「水呢」「你贏了」）是角色的聲音，
口語是刻意的——那是這個工具的設計核心之一，不在這支的管轄範圍。

**介面本身的文案**（設定項的標題與說明、選單項目、按鈕）是標籤，不是對話。
規則：

- **名詞或動詞片語，不是句子。**「開機時啟動」不是「開機之後會自動幫你開起來」
- **不用第二人稱。** 介面不對使用者說話，它只標示自己
- **不解釋機制或後果。** 「這個值影響什麼」講完就停；理由屬於 README
- **不用語助詞。**

## 為什麼要用機器守

這條規則我寫在 SettingsPage 的 docstring 裡，然後自己違反了兩次
（「關掉之後要自己從開始選單開它」「睡前 2–3 小時攝取水分才是造成夜間起身的
原因，所以…」）。**寫在註解裡的規則擋不住任何人，包括寫下它的人。**

檢出的是徵狀不是全部——沒有正規表達式能判斷一句話夠不夠專業。
但第二人稱與語助詞是精準的訊號，抓到就一定是。
"""
import io
import os
import re
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
APP = r"E:\Claude Project\Claude Inbox\喝水提醒桌寵"
sys.path.insert(0, APP)

# island.py 也在檢查範圍內，但它含角色台詞——那些用
# `# copy-style: off` / `on` 標出來，見該檔的 MESSAGES 區段。
TARGETS = ("stats_window.py", "menu.py", "island.py")

BANNED = {
    "你": "第二人稱：介面不對使用者說話",
    "妳": "第二人稱：介面不對使用者說話",
    "自己": "第二人稱／口語",
    "就會": "口語的因果連接",
    "才會": "口語的因果連接",
    "不然": "口語的因果連接",
    "之後要": "口語的因果連接",
    "管不到": "口語",
    "喔": "語助詞",
    "吧": "語助詞",
    "囉": "語助詞",
}

STRING = re.compile('"([^"]{3,})"')
CJK = re.compile("[\u4e00-\u9fff]")

fails = []
checked = 0

for name in TARGETS:
    path = os.path.join(APP, name)
    in_doc = False
    off = False
    for lineno, line in enumerate(io.open(path, encoding="utf-8"), 1):
        # 角色台詞用 pragma 標出來。**不是網開一面，是換一套標準**：
        # 島說「口渴了」「你贏了」是設計的一部分，那些字要口語才對。
        if "copy-style: off" in line:
            off = True
            continue
        if "copy-style: on" in line:
            off = False
            continue
        if off:
            continue
        # 跳過 docstring 與註解：那裡是寫給維護者看的，本來就該把理由講完。
        # 單行 docstring 的兩個引號在同一行，不能只看「有沒有出現」就翻轉狀態——
        # 第一版就是這樣把一句 docstring 誤報成介面文案。
        marks = line.count('"""')
        if marks >= 2:
            continue                      # 單行 docstring，狀態不變
        if marks == 1:
            in_doc = not in_doc
            continue
        if in_doc or line.lstrip().startswith("#"):
            continue
        for m in STRING.finditer(line):
            text = m.group(1)
            if not CJK.search(text) or "{" in text:
                continue        # 純 ASCII（樣式表、鍵名）與 f-string 樣板跳過
            checked += 1
            for word, why in BANNED.items():
                if word in text:
                    fails.append((name, lineno, text, word, why))

print(f"檢查了 {checked} 個介面字串")
for name, lineno, text, word, why in fails:
    print(f"  FAIL {name}:{lineno}  「{text}」")
    print(f"       含「{word}」—— {why}")

print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 個字串不合風格"))
sys.exit(1 if fails else 0)

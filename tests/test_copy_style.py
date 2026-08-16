# -*- coding: utf-8 -*-
"""介面文案的風格檢查。

## 兩種文案，兩套標準

島的訊息（`island.MESSAGES`：「口渴了」「水呢」「你贏了」）是角色的聲音，
口語是刻意的——那是這個工具的設計核心之一，不在這支的管轄範圍。

介面本身的文案（設定項的標題與說明、選單項目、按鈕）是標籤，不是對話。
規則：

- 名詞或動詞片語，不是句子。「開機時啟動」不是「開機之後會自動幫你開起來」
- 不用第二人稱。介面不對使用者說話，它只標示自己
- 不解釋機制或後果。「這個值影響什麼」講完就停；理由屬於 README
- 不用語助詞。

## 為什麼要用機器守

這條規則我寫在 SettingsPage 的 docstring 裡，然後自己違反了兩次
（「關掉之後要自己從開始選單開它」「睡前 2–3 小時攝取水分才是造成夜間起身的
原因，所以…」）。寫在註解裡的規則擋不住任何人，包括寫下它的人。

檢出的是徵狀不是全部——沒有正規表達式能判斷一句話夠不夠專業。
但第二人稱與語助詞是精準的訊號，抓到就一定是。
"""
import io
import os
import re
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "src")
sys.path.insert(0, APP)

# island.py 也在檢查範圍內，但它含角色台詞——那些用
# `# copy-style: off` / `on` 標出來，見該檔的 MESSAGES 區段。
TARGETS = ("stats_window.py", "menu.py", "island.py", "onboard.py")

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
    "—": "破折號：介面用標點分隔，不用破折號",
    "–": "破折號：介面用標點分隔，不用破折號",
}

# 不能用一個字代替一個詞。單字看起來省，但它把「這是什麼」的判斷丟給讀者：
# 「島顯示在」的島是什麼島？讀過整份文件的人知道，第一次打開設定的人不知道。
# key 是那個單字，value 是 (完整的詞, 例外前綴)——前綴出現時代表它本來就是
# 完整詞的一部分，不算違規。
SHORTHAND = {
    "島": ("動態島", "態"),
}

STRING = re.compile('"([^"]{3,})"')
CJK = re.compile("[\u4e00-\u9fff]")


def restated(text):
    """\u9017\u865f\u5169\u908a\u51fa\u73fe\u540c\u4e00\u500b\u8a5e\uff0c\u591a\u534a\u662f\u5f8c\u534a\u53e5\u628a\u524d\u534a\u53e5\u518d\u8b1b\u4e00\u6b21\u3002

    \u6293\u5230\u904e\u7684\u5be6\u4f8b\uff1a\u300c\u4ee5\u5728\u96fb\u8166\u524d\u7684\u6642\u9593\u8a08\u7b97\uff0c\u96e2\u958b\u96fb\u8166\u4e0d\u7b97\u300d\u2014\u2014
    \u7b2c\u4e00\u53e5\u5df2\u7d93\u628a\u8a71\u8aaa\u5b8c\uff0c\u7b2c\u4e8c\u53e5\u53ea\u662f\u63db\u500b\u8aaa\u6cd5\u91cd\u8907\uff0c\u8b80\u7684\u4eba\u5f97\u8b80\u5169\u904d\u624d\u78ba\u5b9a\u6c92\u6709\u65b0\u8cc7\u8a0a\u3002

    \u9019\u662f\u5197\u8d05\u4e0d\u662f\u7528\u8a5e\u4e0d\u7576\uff0c\u6240\u4ee5\u4e0a\u9762\u90a3\u4efd\u9055\u7981\u8a5e\u6e05\u55ae\u6293\u4e0d\u5230\u5b83\u3002
    \u7528\u300c\u5169\u500b\u5b50\u53e5\u5171\u7528\u4e00\u500b\u96d9\u5b57\u8a5e\u300d\u7576\u8a0a\u865f\uff1a\u5be6\u6e2c\u5c0d\u73fe\u6709\u7684\u6240\u6709\u591a\u5b50\u53e5\u6587\u6848\u96f6\u8aa4\u5831
    \uff08\u300c\u79fb\u9664\u6240\u6709\u88dc\u6c34\u7d00\u9304\u8207\u9023\u7e8c\u5929\u6578\uff0c\u8a2d\u5b9a\u4fdd\u7559\u300d\u300c\u63a8\u4f30\u503c\uff0c\u7d2f\u7a4d\u8db3\u5920\u7d00\u9304\u5f8c\u81ea\u52d5\u6821\u6e96\u300d
    \u9019\u4e9b\u90fd\u662f\u524d\u5f8c\u5404\u8b1b\u4e00\u4ef6\u4e8b\uff0c\u4e0d\u6703\u5171\u7528\u8a5e\uff09\u3002

    \u56de\u50b3\u5171\u7528\u7684\u90a3\u500b\u8a5e\uff0c\u6c92\u6709\u5c31\u56de None\u3002
    """
    parts = [p for p in re.split("[\uff0c\u3002]", text) if len(p) >= 4]
    for i, a in enumerate(parts):
        grams_a = {a[k:k + 2] for k in range(len(a) - 1) if CJK.match(a[k:k + 2] or " ")}
        grams_a = {g for g in grams_a if len(g) == 2 and CJK.match(g[0]) and CJK.match(g[1])}
        for b in parts[i + 1:]:
            grams_b = {b[k:k + 2] for k in range(len(b) - 1)}
            shared = grams_a & grams_b
            if shared:
                return sorted(shared)[0]
    return None

fails = []
checked = 0

for name in TARGETS:
    path = os.path.join(APP, name)
    in_doc = False
    off = False
    for lineno, line in enumerate(io.open(path, encoding="utf-8"), 1):
        # 角色台詞用 pragma 標出來。不是網開一面，是換一套標準：
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
            for short, (full, prefix) in SHORTHAND.items():
                for m in re.finditer(short, text):
                    if m.start() == 0 or text[m.start() - 1] != prefix:
                        fails.append((name, lineno, text, short,
                                      f"用單字代替詞：請寫「{full}」"))
                        break
            dup = restated(text)
            if dup:
                fails.append((name, lineno, text, dup,
                              "冗贅：逗號兩邊都出現這個詞，後半句多半沒有新資訊"))

print(f"檢查了 {checked} 個介面字串")
for name, lineno, text, word, why in fails:
    print(f"  FAIL {name}:{lineno}  「{text}」")
    print(f"       含「{word}」—— {why}")

print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 個字串不合風格"))
sys.exit(1 if fails else 0)

# -*- coding: utf-8 -*-
"""驗證檢查更新：版本解析、比較、挑最新的、以及**失敗時絕不吵人**。

這一整支不碰網路。`fetch()` 收 opener 參數就是為了這件事——真的去打 GitHub
的測試會隨對方的狀態時好時壞，而那種測試比沒有測試更糟。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

sys.stdout.reconfigure(errors="replace")

import updates  # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(("  ok   " if ok else "  FAIL ") + f"{label}: {got!r}" +
          ("" if ok else f"  (預期 {want!r})"))
    if not ok:
        fails.append(label)


print("1. 版本號解析")
check("帶 v", updates.parse_version("v0.10.1-beta"), ((0, 10, 1), True))
check("不帶 v", updates.parse_version("0.10.1-beta"), ((0, 10, 1), True))
check("正式版", updates.parse_version("1.0.0"), ((1, 0, 0), False))
check("前後空白", updates.parse_version("  v2.3.4  "), ((2, 3, 4), False))
# 看不懂一律 None，不要猜。猜錯的下場是叫使用者去下載一個不存在的版本。
check("位數不足", updates.parse_version("0.1"), None)
check("位數過多", updates.parse_version("0.1.2.3"), None)
check("不是數字", updates.parse_version("0.a.1"), None)
check("空字串", updates.parse_version(""), None)
check("None", updates.parse_version(None), None)
check("不是字串", updates.parse_version(123), None)

print("\n2. 誰比較新")
check("次版本升級", updates.is_newer("0.11.0", "0.10.1-beta"), True)
check("修訂號升級", updates.is_newer("0.10.2-beta", "0.10.1-beta"), True)
check("主版本升級", updates.is_newer("1.0.0", "0.10.1-beta"), True)
check("一樣", updates.is_newer("0.10.1-beta", "0.10.1-beta"), False)
check("比較舊", updates.is_newer("0.10.0-beta", "0.10.1-beta"), False)
# 數字相同時，正式版比預發布新。這是 SemVer 的規則，也是直覺：
# 0.10.1 是 0.10.1-beta 轉正之後的那一版。
check("正式版勝過同號的預發布",
      updates.is_newer("0.10.1", "0.10.1-beta"), True)
check("預發布不會勝過同號的正式版",
      updates.is_newer("0.10.1-beta", "0.10.1"), False)
# **任何一邊看不懂就回 False。** 說錯的代價（叫人去下載不存在的版本）
# 比不說大得多。
check("候選看不懂", updates.is_newer("abc", "0.10.1-beta"), False)
check("目前版本看不懂", updates.is_newer("0.11.0", "???"), False)
check("兩邊都是 None", updates.is_newer(None, None), False)

print("\n3. 從清單挑最新的")


def rel(tag, draft=False, url="https://example.invalid/x"):
    return {"tag_name": tag, "html_url": url, "draft": draft}


check("單筆", updates.pick_newest([rel("v0.10.1-beta")]),
      ("v0.10.1-beta", "https://example.invalid/x"))
# **不能直接拿第一筆。** API 是照建立時間排的，而補發一個舊版的修訂
# 會讓最新建立的那筆不是版本號最大的。
check("順序打亂仍挑得對",
      updates.pick_newest([rel("v0.9.0-beta"), rel("v0.11.0"),
                           rel("v0.10.1-beta")])[0], "v0.11.0")
check("跳過草稿",
      updates.pick_newest([rel("v0.99.0", draft=True),
                           rel("v0.10.1-beta")])[0], "v0.10.1-beta")
check("跳過看不懂的 tag",
      updates.pick_newest([rel("nightly"), rel("v0.10.1-beta")])[0],
      "v0.10.1-beta")
check("沒有 html_url 就跳過",
      updates.pick_newest([{"tag_name": "v9.9.9"}, rel("v0.10.1-beta")])[0],
      "v0.10.1-beta")
check("空清單", updates.pick_newest([]), None)
check("None", updates.pick_newest(None), None)
check("全部看不懂", updates.pick_newest([rel("nightly"), rel("latest")]), None)

print("\n4. 問不到的時候不能吵人，也不能炸")
# 這是整支測試最重要的一節。這個功能沒有人在等它，所以它壞掉時唯一正確的
# 行為是安靜放棄——但**安靜放棄不等於可以拋例外**，例外會往上炸到呼叫端。
GOOD = json.dumps([rel("v0.11.0")])


def boom():
    raise OSError("模擬沒有網路")


def timeout():
    import urllib.error
    raise urllib.error.URLError("timed out")


check("正常回應解得出來", updates.fetch(opener=lambda: GOOD)[0], "v0.11.0")
check("壞掉的 JSON", updates.fetch(opener=lambda: "{{{"), None)
check("回傳不是清單", updates.fetch(opener=lambda: '{"a": 1}'), None)
check("空清單", updates.fetch(opener=lambda: "[]"), None)
check("清單裡不是物件", updates.fetch(opener=lambda: '[1, 2, 3]'), None)
check("沒有網路", updates.fetch(opener=boom), None)
check("逾時", updates.fetch(opener=timeout), None)

print("\n5. 背景查詢")
# Checker 用真的執行緒，所以要等它做完。用 join 而不是 sleep：
# sleep 猜時間，在慢的機器上會時好時壞。
import threading  # noqa: E402


def run_and_wait(c, fetcher):
    c.start(fetcher=fetcher)
    for t in threading.enumerate():
        if t.name == "sipbar-update-check":
            t.join(timeout=5)


c1 = updates.Checker()
check("還沒開始查 -> 未啟用", c1.status(), "未啟用")
run_and_wait(c1, lambda: ("v99.0.0", "https://example.invalid/new"))
check("查完了", c1.finished(), True)
check("狀態是成功", c1.status(), "成功")
check("真的比較新 -> 回傳它", c1.newer_release()[0], "v99.0.0")

c2 = updates.Checker()
run_and_wait(c2, lambda: ("v0.0.1", "https://example.invalid/old"))
# 查得到但比較舊：狀態是成功（查詢本身沒問題），但沒有新版可以講。
check("查得到但比較舊 -> 狀態仍是成功", c2.status(), "成功")
check("查得到但比較舊 -> 不回傳", c2.newer_release(), None)

c3 = updates.Checker()
run_and_wait(c3, lambda: None)
check("查不到 -> 狀態是失敗", c3.status(), "失敗")
check("查不到 -> 不回傳", c3.newer_release(), None)

c4 = updates.Checker()
calls = []
c4.start(fetcher=lambda: calls.append(1) or None)
c4.start(fetcher=lambda: calls.append(1) or None)
for t in threading.enumerate():
    if t.name == "sipbar-update-check":
        t.join(timeout=5)
# 每次啟動問一次就夠。重複呼叫會多打 GitHub 一次，而它有每小時 60 次的上限。
check("重複呼叫只查一次", len(calls), 1)

print("\n6. 端點不能換成 /releases/latest")
# **這一條是這個功能最容易被改壞的地方。** /releases/latest 排除 prerelease，
# 而這個專案發出去的每一版都是 prerelease——用它會拿到 404，而失敗是安靜的，
# 於是整個功能永遠不運作也永遠沒人發現。2026-08-20 實測確認過那個 404。
check("用的是列表端點", updates.RELEASES_API.endswith("/releases"), True)
check("不是 /releases/latest",
      updates.RELEASES_API.endswith("/latest"), False)

print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 項失敗：{fails}"))
sys.exit(1 if fails else 0)

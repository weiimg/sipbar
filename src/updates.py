# -*- coding: utf-8 -*-
"""檢查有沒有新版。**只檢查，不下載，不安裝。**

## 為什麼不做自動更新

攜帶版沒有安裝程式，更新就是解壓縮覆蓋。要自動做的話，執行中的 exe 沒辦法
覆蓋自己，得再生一支 helper 出來換檔、關掉本體、重開——那是一整個子系統。

更關鍵的是**這支執行檔沒有數位簽章**。一個沒簽章、又會自己下載並替換自己的
程式，等於幫自己蓋了一條配送惡意程式的管道：GitHub 帳號被盜、或下載過程被
攔截，使用者的電腦就自動裝上去了。只做檢查、讓人自己點下載，中間就一定有
一雙眼睛，而 SECURITY.md 附的 SHA256 也才有意義。

## 為什麼不用 /releases/latest

那個端點**排除 prerelease**，而這個專案發出去的每一版都是 prerelease
（還在 beta）。用它會拿到 404，而這裡的失敗是設計成安靜的——於是整個功能
永遠不會運作，也永遠不會有人發現。2026-08-20 實測確認過那個 404。

所以讀列表端點，自己挑版本號最大的那一個。
"""

import json
import threading
import urllib.error
import urllib.request

import settings

# 列表端點。不要換成 /releases/latest，理由見模組開頭。
RELEASES_API = "https://api.github.com/repos/weiimg/sipbar/releases"

# 逾時給得短。這是一個沒有人在等的背景查詢，卡住比查不到更糟。
TIMEOUT_S = 8


def parse_version(text):
    """把 "v0.10.1-beta" 拆成 ((0, 10, 1), 是不是預發布)。看不懂回 None。"""
    if not isinstance(text, str):
        return None
    text = text.strip()
    if text[:1] in ("v", "V"):
        text = text[1:]
    core, _, pre = text.partition("-")
    parts = core.split(".")
    if len(parts) != 3:
        return None
    try:
        return tuple(int(p) for p in parts), bool(pre)
    except ValueError:
        return None


def is_newer(candidate, current):
    """candidate 比 current 新嗎。

    **任何一邊看不懂就回 False。** 這個判斷唯一的產出是「要不要跟使用者說有
    新版」，而說錯的代價（叫他去下載一個其實不存在的版本）比不說大得多。
    """
    a, b = parse_version(candidate), parse_version(current)
    if a is None or b is None:
        return False
    if a[0] != b[0]:
        return a[0] > b[0]
    # 數字一樣時，正式版比預發布新：0.10.1 > 0.10.1-beta。
    return b[1] and not a[1]


def pick_newest(releases):
    """從 API 回來的清單挑出版本號最大的那一個。回傳 (tag, 網址) 或 None。

    不直接拿第一筆：API 是照建立時間排的，而**建立時間跟版本號不保證同向**
    ——補發一個舊版的修訂、或把草稿補上去，都會讓最新建立的那筆不是版本最大的。
    """
    best = None
    for rel in releases or ():
        if not isinstance(rel, dict) or rel.get("draft"):
            continue
        tag, url = rel.get("tag_name"), rel.get("html_url")
        ver = parse_version(tag)
        if ver is None or not url:
            continue
        if best is None or is_newer(tag, best[0]):
            best = (tag, url)
    return best


def fetch(timeout=TIMEOUT_S, opener=None):
    """去問 GitHub。回傳 (tag, 網址)，問不到回 None。**不拋例外。**

    opener 只給測試用，正式呼叫端不要傳。
    """
    try:
        if opener is None:
            req = urllib.request.Request(RELEASES_API, headers={
                "Accept": "application/vnd.github+json",
                # 帶上自己的名字是網路禮貌，也讓對方在需要時擋得掉。
                # **不帶任何識別使用者的東西**，那是一個查版本號的請求，
                # 沒有理由知道是誰在問。
                "User-Agent": "Sipbar/%s" % settings.VERSION,
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
        else:
            raw = opener()
        return pick_newest(json.loads(raw))
    except (urllib.error.URLError, OSError, ValueError, TypeError, KeyError):
        # 沒網路、逾時、被限流、回傳格式變了——全部一視同仁地安靜放棄。
        # 這是背景查詢，失敗不該打擾任何人，下次啟動再問一次就好。
        return None


class Checker:
    """在背景問一次，結果放著等介面來拿。

    用一條普通的執行緒而不是 Qt 的網路元件：這條路上完全不碰任何 Qt 物件，
    所以沒有跨執行緒動 UI 的問題——它只寫兩個字串，由主執行緒自己來讀。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._result = None
        self._done = False
        self._started = False

    def start(self, fetcher=None):
        """開始查。重複呼叫只查一次（每次啟動問一次就夠了）。"""
        if self._started:
            return
        self._started = True
        fetcher = fetcher or fetch

        def work():
            found = fetcher()
            with self._lock:
                self._result = found
                self._done = True

        t = threading.Thread(target=work, name="sipbar-update-check", daemon=True)
        t.start()

    def newer_release(self):
        """有新版就回 (tag, 網址)，其餘一律 None（還沒查完也是 None）。"""
        with self._lock:
            if not self._done or not self._result:
                return None
            tag, url = self._result
        return (tag, url) if is_newer(tag, settings.VERSION) else None

    def finished(self):
        """查完了沒。介面用它分辨「還在查」與「查過了，已經是最新版」。"""
        with self._lock:
            return self._done

    def status(self):
        """給診斷資訊的一句話。

        **這一行不是附加的。** 這個功能失敗時是安靜的（沒網路、被限流、
        GitHub 改了回傳格式都一律安靜放棄），所以它哪天靜靜停止運作，
        沒有任何人會發現——包括開發者。而「安靜地不再運作」正是這個專案
        這週修掉的那三個 bug 共同的形狀。

        `_result` 是 None 就代表 fetch() 失敗了：查得到的話它會回最新的那一版，
        即使那一版並不比現在新。所以這裡分得出「查不到」與「已是最新」。
        """
        if not self._started:
            return "未啟用"
        with self._lock:
            if not self._done:
                return "查詢中"
            return "成功" if self._result else "失敗"


# 每個行程一份。島啟動時叫 start()，介面各處讀 newer_release()。
# 測試要自己的實例就直接 Checker()，不要動這一個。
checker = Checker()

# -*- coding: utf-8 -*-
"""喝水紀錄的統計計算 — 只負責從 events.jsonl 算出數字，不負責畫。

畫的部分在 stats_window.py（原生 Qt 視窗）。
初版是產 HTML 用瀏覽器開，但使用者的 .html 關聯到已退場的 Internet Explorer，
`webbrowser.open()` 靜默失敗；改成原生視窗後這一整類依賴都消失了。

成就感的來源排序：
    1. 熱力圖 —— 看到自己累積的軌跡，這是最強的
    2. 連續天數 —— 損失趨避
    3. 徽章 —— 附加，實際行為影響很小

補救額度是這裡最關鍵的機制。自我追蹤系統最大的死因不是忘記，
是「都破功了乾脆算了」那個崩盤。每月給 2 次自動補救，斷一天不會歸零。
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

import settings

MONTHLY_SAVES = 2
HEATMAP_WEEKS = 12

# 0.9.0-beta 的 DEFAULTS["daily_target_drinks"]。事件裡沒記 target 的日子都是
# 那一版留下的資料，一律用這個值回判，不要用「現在的目標」——用現在的目標就是
# 這次要修掉的 bug 本身。
LEGACY_TARGET = 7

# 活躍日的最短運行時間。程式跑不到這個時數的日子，資料量不足以判斷成敗。
#
# 這個數字是量出來的。實測資料裡，有實際使用的日子程式跑了 10.2 與 6.5 小時，
# 幾乎沒開的日子是 3.4、2.3、1.9 小時——兩群之間有一道明顯的縫，門檻放在縫上。
#
# 只有一份使用者的資料，樣本小。要調整的話依據是同一件事：
# 「這一天的程式運行時間，有沒有長到足以代表一天的使用」。
MIN_ACTIVE_SPAN_H = 4.0


# ---------------------------------------------------------------- 讀資料

def _day_key(dt, rollover_hour):
    d = dt - timedelta(days=1) if dt.hour < rollover_hour else dt
    return d.strftime("%Y-%m-%d")


def load_days(events_path, rollover_hour):
    """把事件紀錄整理成 {日期: 當天彙總}。"""
    days = {}
    if not os.path.exists(events_path):
        return days

    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            key = row.get("day")
            if not key:
                continue
            # 改設定不算「那天有在用這個工具」。setdefault 會讓任何帶 day 的事件
            # 都變成一筆當日紀錄，而有紀錄卻沒達標的日子會吃掉一個補救額度——
            # 在一個原本沒開電腦的日子改個設定，就莫名其妙損失一個護盾。
            if row.get("event") == "config":
                continue
            d = days.setdefault(key, {
                "drinks": 0, "reminds": 0, "responded": 0,
                "waits": [], "collapses": 0, "hours": [],
                "target": None, "first_ts": None, "last_ts": None,
            })

            # 當天的目標。取最後一筆是刻意的：目標在當天中途被調過的話，
            # 以使用者最後的意思為準。沒有這個欄位的日子是 0.9.0-beta 留下的。
            if row.get("target"):
                d["target"] = row["target"]

            # 程式當天實際跑了多久，用來判斷這天的資料夠不夠格下結論。
            # config 事件在上面就被跳掉了，改設定不會把跨度撐開。
            try:
                ts = datetime.fromisoformat(row["ts"])
                if d["first_ts"] is None or ts < d["first_ts"]:
                    d["first_ts"] = ts
                if d["last_ts"] is None or ts > d["last_ts"]:
                    d["last_ts"] = ts
            except (KeyError, ValueError):
                pass

            ev = row.get("event")
            if ev == "remind":
                d["reminds"] += 1
            elif ev == "collapse":
                d["collapses"] += 1
            elif ev == "drink":
                d["drinks"] += 1
                if row.get("responded"):
                    d["responded"] += 1
                    d["waits"].append(row.get("wait_active_s", 0))
                try:
                    d["hours"].append(datetime.fromisoformat(row["ts"]).hour)
                except (KeyError, ValueError):
                    pass

    for d in days.values():
        if d["first_ts"] and d["last_ts"]:
            d["span_h"] = (d["last_ts"] - d["first_ts"]).total_seconds() / 3600
    return days


# ---------------------------------------------------------------- 逐日判定

def day_target(info, key, today_key, current_target):
    """這一天當初的目標次數。

    達標與否必須用「當天的目標」判，不能用「現在的目標」。

    用現在的目標的話，調一次體重或單次水量就會把整段歷史重判一次。舉例：
    單次水量從 200ml 改成 150ml，65kg 推出的目標就從 7 變 9——於是所有喝了
    7 次的日子，昨天還是滿分，今天全部變成未達標，而且各吃掉一個補救額度。
    **沒有任何提示。**

    這是結構問題不是統計問題：只要目標是即時推導的，而判定又拿它套用到歷史，
    這件事就會發生。

    沒有記錄的日子分兩種：今天用現在的設定（使用者知道自己在用哪個目標），
    過去的一律用 LEGACY_TARGET。
    """
    if info.get("target"):
        return info["target"]
    return current_target if key == today_key else LEGACY_TARGET


def is_active(info):
    """這一天有沒有在用這個工具。決定它出不出現在統計、熱圖與分頁上。"""
    return bool(info["drinks"] or info["reminds"])


def is_judgeable(info, target):
    """這一天的資料夠不夠格拿來判定成敗。

    有些日子程式只開了一兩個小時：發出 1 次提醒、回應 1 次就關掉。它有事件，
    於是被當成正常的一天判成未達標並吃掉一個補救額度；而同一天的回應率
    算出來是 100%（1 除以 1）。一天不可能既完美又失敗，問題是那天根本
    沒有足夠的資料下任何結論。

    **不夠格判定 ≠ 沒在用。** 那天仍然會出現在紀錄與熱圖上（它確實發生過），
    只是不拿來判斷達標與否，也不消耗補救額度。兩件事混在一起會造成新的災情：
    新使用者裝好第一個小時喝了兩次，跨度不到門檻也還沒達標，紀錄視窗會告訴
    他「還沒有任何紀錄」——明明有。

    達標的日子無條件算數：在電腦前只待 3 小時卻喝滿目標，那是成功不是沒資料。
    span_h 不存在時視為夠格，寧可算進來也不要無聲地把日子吃掉。
    """
    if info["drinks"] >= target:
        return True
    span = info.get("span_h")
    return span is None or span >= MIN_ACTIVE_SPAN_H


# ---------------------------------------------------------------- 連續天數

def compute_streaks(days, target, today_key, monthly_saves=MONTHLY_SAVES):
    """一趟往前走，同時算出「目前連續」與「最長連續」。

    刻意用同一趟算：分成兩個函式各自跑，補救額度的消耗方式會不一樣，
    就會出現「目前連續 4 天、最長連續 3 天」這種自相矛盾的數字，
    而數字一自相矛盾，整個後台的可信度就沒了。
    這樣寫的結構保證「目前」永遠是最後一段，不可能超過「最長」。

    三條規則讓它不會變成懲罰機器：
    - 完全沒有紀錄的日子（拍攝日、電腦沒開）視為中性，跳過不算斷。
    - 有紀錄但資料不足以判定的日子也視為中性，理由見 is_judgeable()。
    - 有紀錄、判得出來但沒達標的日子，每月 2 次補救額度，用掉就保住連續。

    target 是「現在的目標」，只在某天沒有留下自己的目標時當 fallback 用，
    判定一律以當天的目標為準——理由見 day_target()。
    """
    tgt = {k: day_target(v, k, today_key, target) for k, v in days.items()}
    keys = sorted(k for k, v in days.items() if is_active(v))
    runs, run, saved_days = [], 0, []
    used = defaultdict(int)

    for key in keys:
        info = days[key]
        if info["drinks"] >= tgt[key]:
            run += 1
            continue
        if key == today_key:
            continue                              # 今天還在進行中，不算斷也不算成
        if not is_judgeable(info, tgt[key]):
            continue                              # 資料不足，中性：不算斷，也不吃護盾
        month = key[:7]
        if used[month] < monthly_saves:
            used[month] += 1
            saved_days.append(key)                # 補救掉，連續保住但這天不計入
            continue
        runs.append(run)
        run = 0

    runs.append(run)                              # 最後一段就是目前的連續
    return {
        "streak": run,
        "longest": max(runs),
        "saved_days": saved_days,
        "saves_left": max(0, monthly_saves - used[today_key[:7]]),
        "saves_total": monthly_saves,
    }


# ---------------------------------------------------------------- 彙總

def compute(cfg, events_path):
    target = cfg["daily_target_drinks"]
    ml = cfg["ml_per_drink_estimate"]
    rollover = settings.DAY_ROLLOVER_HOUR

    days = load_days(events_path, rollover)
    today_key = _day_key(datetime.now(), rollover)
    today = days.get(today_key, {"drinks": 0, "reminds": 0, "responded": 0,
                                 "waits": [], "collapses": 0, "hours": []})

    tgt = {k: day_target(v, k, today_key, target) for k, v in days.items()}
    active = {k: v for k, v in days.items() if is_active(v)}
    total_drinks = sum(v["drinks"] for v in active.values())
    total_reminds = sum(v["reminds"] for v in active.values())
    total_responded = sum(v["responded"] for v in active.values())
    all_waits = [w for v in active.values() for w in v["waits"]]
    hit_days = sum(1 for k, v in active.items() if v["drinks"] >= tgt[k])

    streak_info = compute_streaks(days, target, today_key)

    hours = defaultdict(int)
    for v in active.values():
        for h in v["hours"]:
            hours[h] += 1

    return {
        "target": target,
        "ml": ml,
        "today_key": today_key,
        "today": today,
        "days": days,
        "active_days": len(active),
        "hit_days": hit_days,
        "total_drinks": total_drinks,
        "total_reminds": total_reminds,
        "total_responded": total_responded,
        "avg_wait_min": (sum(all_waits) / len(all_waits) / 60) if all_waits else None,
        "rate": (total_responded / total_reminds) if total_reminds else None,
        "streak": streak_info,
        "longest": streak_info["longest"],
        "hours": dict(hours),
        "collapses": sum(v["collapses"] for v in active.values()),
    }


# ---------------------------------------------------------------- 成就

def achievements(data):
    """回傳 (名稱, 說明, 目前進度, 目標)。

    每一項都要能算出「還差多少」——「再 2 天就解鎖」比一顆灰掉的徽章
    有力得多。全部用正向累積，不放「失敗了幾次」那種計數。
    """
    t = data["target"]
    best_day = max((v["drinks"] for v in data["days"].values()), default=0)
    return [
        ("第一次記錄", "完成一次補水", min(1, data["total_drinks"]), 1),
        ("單日達標", f"一天內補水 {t} 次", min(best_day, t), t),
        ("連續 3 天", "連續三天達標", min(data["longest"], 3), 3),
        ("連續 7 天", "連續七天達標", min(data["longest"], 7), 7),
        ("累積 100 次", "總補水次數達 100", min(data["total_drinks"], 100), 100),
        ("連續 30 天", "連續三十天達標", min(data["longest"], 30), 30),
    ]


def week_days(data):
    """本週七天（一到日）的狀態，給週曆用。"""
    today = datetime.strptime(data["today_key"], "%Y-%m-%d")
    monday = today - timedelta(days=today.weekday())
    out = []
    for i in range(7):
        d = monday + timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        info = data["days"].get(key)
        used = bool(info and (info["drinks"] or info["reminds"]))
        out.append({
            "key": key,
            "label": "一二三四五六日"[i],
            "drinks": info["drinks"] if info else 0,
            "used": used,
            "future": d > today,
            "today": key == data["today_key"],
            "hit": bool(info and info["drinks"] >= data["target"]),
        })
    return out

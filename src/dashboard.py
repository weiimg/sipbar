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

MONTHLY_SAVES = 2
HEATMAP_WEEKS = 12


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
            })
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
    return days


# ---------------------------------------------------------------- 連續天數

def compute_streaks(days, target, today_key, monthly_saves=MONTHLY_SAVES):
    """一趟往前走，同時算出「目前連續」與「最長連續」。

    刻意用同一趟算：分成兩個函式各自跑，補救額度的消耗方式會不一樣，
    就會出現「目前連續 4 天、最長連續 3 天」這種自相矛盾的數字，
    而數字一自相矛盾，整個後台的可信度就沒了。
    這樣寫的結構保證「目前」永遠是最後一段，不可能超過「最長」。

    兩條規則讓它不會變成懲罰機器：
    - 完全沒有紀錄的日子（拍攝日、電腦沒開）視為中性，跳過不算斷。
    - 有紀錄但沒達標的日子，每月 2 次補救額度，用掉就保住連續。
    """
    keys = sorted(k for k, v in days.items() if v["drinks"] or v["reminds"])
    runs, run, saved_days = [], 0, []
    used = defaultdict(int)

    for key in keys:
        info = days[key]
        if info["drinks"] >= target:
            run += 1
            continue
        if key == today_key:
            continue                              # 今天還在進行中，不算斷也不算成
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
    rollover = cfg["day_rollover_hour"]

    days = load_days(events_path, rollover)
    today_key = _day_key(datetime.now(), rollover)
    today = days.get(today_key, {"drinks": 0, "reminds": 0, "responded": 0,
                                 "waits": [], "collapses": 0, "hours": []})

    active = {k: v for k, v in days.items() if v["drinks"] or v["reminds"]}
    total_drinks = sum(v["drinks"] for v in active.values())
    total_reminds = sum(v["reminds"] for v in active.values())
    total_responded = sum(v["responded"] for v in active.values())
    all_waits = [w for v in active.values() for w in v["waits"]]
    hit_days = sum(1 for v in active.values() if v["drinks"] >= target)

    streak_info = compute_streaks(days, target, today_key)

    # Phase 1 判準：連續 3 天回應率 > 50%。
    #
    # 這個數字不可信，不要拿它做決定，真正的訊號是上面的 hit_days。理由見
    # docs/DESIGN.md 的「判準」，摘要：分母是 reminds（程式問了幾次），
    # 不是每日目標。程式沒在跑就不會問，分母跟著縮小——2026-08-12 整天沒開，
    # 只發出 1 次提醒、回應 1 次，算出 100%，而當天實際補水 1/7 次。
    # 方向還是反的：程式當掉、被關掉、人不在電腦前，這些最該被抓到的失敗
    # 剛好都會讓分母變小，於是失敗越嚴重分數越漂亮。
    #
    # 算式保留原樣是刻意的：紀錄視窗那行灰字還在讀它，改計算會動到畫面上的數字，
    # 那屬於「達標判定凍結在當天」那次修改的範圍，跟這裡的敘述訂正分開做。
    recent = [days[k] for k in sorted(active.keys())[-3:] if days[k]["reminds"] > 0]
    passed = len(recent) == 3 and all(d["responded"] / d["reminds"] > 0.5 for d in recent)

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
        "phase1_passed": passed,
        "phase1_sample": len(recent),
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

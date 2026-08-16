# -*- coding: utf-8 -*-
"""產一組擬真的 5 週資料，渲染後台頁面來看實際長相。"""
import json
import os
import random
import shutil
import sys
from datetime import datetime, timedelta

SCRATCH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dashboard  # noqa: E402
import island as isl  # noqa: E402

OUT = os.path.join(SCRATCH, "wp_dash")
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)
EVENTS = os.path.join(OUT, "events.jsonl")

random.seed(7)
cfg = dict(isl.DEFAULT_CONFIG)
TARGET = cfg["daily_target_drinks"]
today = datetime.now()

rows = []
for back in range(38, -1, -1):
    day = today - timedelta(days=back)
    key = day.strftime("%Y-%m-%d")

    # 拍攝日：電腦沒開，完全沒紀錄
    if random.random() < 0.13:
        continue

    rows.append({"ts": day.replace(hour=9).isoformat(timespec="seconds"),
                 "day": key, "event": "day_start"})

    # 越近期越上手
    skill = 0.42 + (38 - back) / 38 * 0.45
    reminds = random.randint(5, 8)
    drinks = 0
    for i in range(reminds):
        hour = 10 + int(i * (14 / max(1, reminds))) + random.randint(0, 1)
        hour = min(23, hour)
        ts = day.replace(hour=hour, minute=random.randint(0, 59)).isoformat(timespec="seconds")
        rows.append({"ts": ts, "day": key, "event": "remind", "drinks": drinks})

        if random.random() < skill:
            wait = random.randint(30, 1500)
            if wait > 900:
                rows.append({"ts": ts, "day": key, "event": "weak"})
            drinks += 1
            rows.append({"ts": ts, "day": key, "event": "drink", "from_state": "THIRSTY",
                         "responded": True, "wait_active_s": wait, "drinks": drinks})
        elif random.random() < 0.35:
            rows.append({"ts": ts, "day": key, "event": "weak"})
            rows.append({"ts": ts, "day": key, "event": "collapse"})

with open(EVENTS, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

data = dashboard.compute(cfg, EVENTS)
print(f"有紀錄天數 {data['active_days']}　達標 {data['hit_days']}　"
      f"連續 {data['streak']['streak']}　最長 {data['longest']}")
print(f"回應率 {data['rate'] * 100:.0f}%　補救額度剩 {data['streak']['saves_left']}"
      f"　被補救的日子 {len(data['streak']['saved_days'])}")
print("Phase 1 判準:", "過" if data["phase1_passed"] else "未過")

path = os.path.join(OUT, "dashboard.html")
with open(path, "w", encoding="utf-8") as f:
    f.write(dashboard.render_html(data))
print("HTML ->", path)

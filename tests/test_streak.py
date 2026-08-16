# -*- coding: utf-8 -*-
"""連續天數的完整情境測試。

每個情境直接建構 days 字典餵給 compute_streaks，不經過檔案，
才能精準控制「今天」與每一天的狀態。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dashboard  # noqa: E402

T = 7
fails = []


def mk(spec):
    """spec: {日期: 次數}，次數 None 代表那天完全沒開電腦（不會出現在紀錄裡）。"""
    days = {}
    for k, n in spec.items():
        if n is None:
            continue
        days[k] = {"drinks": n, "reminds": max(1, n), "responded": n,
                   "waits": [], "collapses": 0, "hours": []}
    return days


def case(name, spec, today, want_streak, want_longest=None):
    r = dashboard.compute_streaks(mk(spec), T, today)
    ok = r["streak"] == want_streak
    if want_longest is not None:
        ok = ok and r["longest"] == want_longest
    tag = "  ok  " if ok else "  FAIL"
    extra = f"　最長={r['longest']}" if want_longest is None else \
            f"　最長={r['longest']}（預期 {want_longest}）"
    print(f"{tag} {name}：連續={r['streak']}（預期 {want_streak}）{extra}")
    if not ok:
        fails.append(name)
    return r


print("\n1. 基本累積")
case("連 5 天達標", {f"2026-08-0{i}": T for i in range(1, 6)}, "2026-08-05", 5, 5)
case("連 5 天達標，第 6 天還沒開始",
     dict({f"2026-08-0{i}": T for i in range(1, 6)}, **{"2026-08-06": 0}),
     "2026-08-06", 5, 5)
case("連 5 天達標，第 6 天喝到一半",
     dict({f"2026-08-0{i}": T for i in range(1, 6)}, **{"2026-08-06": 3}),
     "2026-08-06", 5, 5)
case("今天達標就立刻計入",
     dict({f"2026-08-0{i}": T for i in range(1, 6)}, **{"2026-08-06": T}),
     "2026-08-06", 6, 6)

print("\n2. 沒開電腦的日子（拍攝日）不算斷")
case("中間兩天完全沒紀錄",
     {"2026-08-01": T, "2026-08-02": None, "2026-08-03": None,
      "2026-08-04": T, "2026-08-05": T},
     "2026-08-05", 3, 3)

print("\n3. 護盾")
case("中間一天沒達標，護盾擋下",
     {"2026-08-01": T, "2026-08-02": 3, "2026-08-03": T, "2026-08-04": T},
     "2026-08-04", 3, 3)
case("同月第三次沒達標，護盾用完就斷",
     {"2026-08-01": T, "2026-08-02": 1, "2026-08-03": T, "2026-08-04": 1,
      "2026-08-05": T, "2026-08-06": 1, "2026-08-07": T},
     "2026-08-07", 1, 3)
r = case("跨月護盾重置",
         {"2026-08-30": 1, "2026-08-31": 1, "2026-09-01": 1, "2026-09-02": T},
         "2026-09-02", 1)
print(f"       被護盾擋下的日子：{r['saved_days']}　本月剩 {r['saves_left']}/{r['saves_total']}")

print("\n4. 長期累積不會每天重置（連續 30 天）")
spec = {}
for i in range(1, 31):
    spec[f"2026-08-{i:02d}"] = T
case("連 30 天", spec, "2026-08-30", 30, 30)

print("\n5. 每天檢查一次，數字必須逐日遞增")
spec = {}
prev = 0
bad = []
for i in range(1, 11):
    spec[f"2026-08-{i:02d}"] = T
    today = f"2026-08-{i:02d}"
    s = dashboard.compute_streaks(mk(spec), T, today)["streak"]
    if s != prev + 1:
        bad.append((today, s, prev + 1))
    prev = s
if bad:
    print(f"  FAIL 有 {len(bad)} 天沒有遞增：{bad}")
    fails.append("逐日遞增")
else:
    print(f"  ok   連續 10 天，每天各查一次都正確遞增（1→{prev}）")

print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 項失敗：{fails}"))
sys.exit(1 if fails else 0)

# -*- coding: utf-8 -*-
"""連續天數的完整情境測試。

每個情境直接建構 days 字典餵給 compute_streaks，不經過檔案，
才能精準控制「今天」與每一天的狀態。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import dashboard  # noqa: E402

T = 7
fails = []


def mk(spec):
    """spec: {日期: 次數}，次數 None 代表那天完全沒開電腦（不會出現在紀錄裡）。

    次數也可以寫成 dict，用來指定當天自己的目標與程式運行跨度：
    `{"drinks": 7, "target": 7, "span_h": 2.9}`。沒寫的欄位照舊——
    target 不記（由 compute_streaks 回填 LEGACY_TARGET），
    span_h 不記（視為夠格判定，見 dashboard.is_judgeable）。
    """
    days = {}
    for k, n in spec.items():
        if n is None:
            continue
        info = n if isinstance(n, dict) else {"drinks": n}
        drinks = info.get("drinks", 0)
        days[k] = {"drinks": drinks, "reminds": max(1, drinks), "responded": drinks,
                   "waits": [], "collapses": 0, "hours": [],
                   "target": info.get("target"), "first_ts": None, "last_ts": None}
        if "span_h" in info:
            days[k]["span_h"] = info["span_h"]
    return days


def case(name, spec, today, want_streak, want_longest=None, target=T):
    r = dashboard.compute_streaks(mk(spec), target, today)
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

print("\n3. 護盾：庫存制，靠達標賺回來，沒有日曆邊界")
# 先前是每月 2 個、1 號重置。那個模式有一道使用者無法預測的懸崖：同樣用掉兩個，
# 1 號用完要裸奔 29 天，30 號用完隔天就補滿。現在照 Duolingo 的 streak freeze：
# 存量制，達標賺回來。
case("中間一天沒達標，護盾擋下",
     {"2026-08-01": T, "2026-08-02": 3, "2026-08-03": T, "2026-08-04": T},
     "2026-08-04", 3, 3)

# 緩衝深度：存滿 2 個，代表連續兩個「真的在電腦前、真的沒喝滿」的日子
# 仍然不會斷，第三個會斷。
#
# 上限刻意不再往上加。一天沒喝滿很常見，兩天連著是小失衡，三天連著是一種狀態
# ——工具這時候還說「你還在連續 12 天」不是鼓勵，是奉承，而本人一定會識破。
case("連續兩天沒達標，還是沒斷",
     {"2026-08-01": T, "2026-08-02": 1, "2026-08-03": 1, "2026-08-04": T},
     "2026-08-04", 2, 2)
case("第三天才斷",
     {"2026-08-01": T, "2026-08-02": 1, "2026-08-03": 1, "2026-08-04": 1,
      "2026-08-05": T},
     "2026-08-05", 1, 1)

r = case("達標會把護盾賺回來",
         {"2026-08-01": T, "2026-08-02": 1, "2026-08-03": T, "2026-08-04": T,
          "2026-08-05": T, "2026-08-06": T},
         "2026-08-06", 5, 5)
if r["saves_left"] != r["saves_total"]:
    print(f"  FAIL 賺回來的沒有存滿：{r['saves_left']}/{r['saves_total']}")
    fails.append("達標沒有把護盾賺回上限")
else:
    print(f"  ok   用掉一個之後又存回上限：{r['saves_left']}/{r['saves_total']}")

# 舊模式在這裡會於 9/1 憑空補滿，於是同一串行為的結果由日曆決定。
r = case("跨月不會憑空補滿",
         {"2026-08-30": 1, "2026-08-31": 1, "2026-09-01": 1, "2026-09-02": 1,
          "2026-09-03": T},
         "2026-09-03", 1, 1)
print(f"       被護盾擋下的日子：{r['saved_days']}　剩 {r['saves_left']}/{r['saves_total']}")

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

print("\n6. 達標與否要凍結在當天，改設定不能回溯改寫歷史")
# 2026-08-15 把 ml_per_drink_estimate 從 200 改成 150，目標從 7 變 9。
# 修好之前，8/10 與 8/11 兩個 7/7 的滿分日會當場變成未達標，還各吃掉一個護盾。
case("目標調高後，過去達到當時目標的日子仍然算達標",
     {"2026-08-10": {"drinks": 7, "target": 7},
      "2026-08-11": {"drinks": 7, "target": 7},
      "2026-08-12": {"drinks": 9, "target": 9}},
     "2026-08-12", 3, 3, target=9)
r = case("舊資料沒記目標，一律用 LEGACY_TARGET 回判，不受現在的目標影響",
         {"2026-08-10": 7, "2026-08-11": 7, "2026-08-12": 9},
         "2026-08-12", 3, 3, target=9)
print(f"       護盾沒有被誤扣：剩 {r['saves_left']}/{r['saves_total']}")

print("\n7. 資料不足的日子是中性，不是失敗")
# 2026-08-12 程式整天沒開，凌晨才啟動跑了 2.9 小時，1 次提醒 1 次補水。
# 修好之前它被判成未達標並吃掉一個護盾，同一天的回應率卻算出 100%。
r = case("程式只跑 3 小時的日子不算斷，也不吃護盾",
         {"2026-08-10": T, "2026-08-11": {"drinks": 1, "span_h": 2.9},
          "2026-08-12": T},
         "2026-08-12", 2, 2)
if r["saves_left"] != r["saves_total"]:
    print(f"  FAIL 護盾被扣了：剩 {r['saves_left']}/{r['saves_total']}")
    fails.append("跨度不足不該吃護盾")
else:
    print(f"  ok   護盾完好：剩 {r['saves_left']}/{r['saves_total']}")
case("只開 2 小時但喝滿目標，仍然算達標",
     {"2026-08-10": T, "2026-08-11": {"drinks": T, "span_h": 2.0},
      "2026-08-12": T},
     "2026-08-12", 3, 3)

print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 項失敗：{fails}"))
sys.exit(1 if fails else 0)

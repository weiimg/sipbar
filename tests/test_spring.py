# -*- coding: utf-8 -*-
"""驗證彈簧：要有輕微過衝、要在合理時間內收斂、不能發散或永遠震盪。"""
import os
import sys

sys.path.insert(0, r"E:\Claude Project\Claude Inbox\喝水提醒桌寵")
# 彈簧原本住在 island_prototype.py（形式評估用的原型），後來抽進 motion.py
# 給島與紀錄視窗共用。原型已經封存，這裡直接測共用的那一份。
import motion as isl  # noqa: E402

DT = 1 / 60.0
fails = []


def run(label, response, damping, expect_overshoot):
    s = isl.Spring(0.0, response, damping)
    s.target = 1.0
    peak, settle_frame, frames = 0.0, None, 0
    for i in range(600):
        s.step(DT)
        frames = i + 1
        peak = max(peak, s.value)
        if settle_frame is None and s.settled:
            settle_frame = i + 1
        if abs(s.value) > 5:
            print(f"  FAIL {label}: 發散（值 {s.value:.2f}）")
            fails.append(label)
            return
        if settle_frame:
            break

    overshoot_pct = (peak - 1.0) * 100
    settle_ms = (settle_frame or frames) * DT * 1000
    ok = True
    if settle_frame is None:
        ok = False
        note = "沒有在 10 秒內收斂"
    elif expect_overshoot and not (1.5 <= overshoot_pct <= 15):
        ok = False
        note = f"過衝 {overshoot_pct:.1f}% 不在 1.5~15% 的合理範圍"
    elif not expect_overshoot and overshoot_pct > 0.6:
        ok = False
        note = f"不該過衝卻衝了 {overshoot_pct:.1f}%"
    elif settle_ms > 1400:
        ok = False
        note = f"收斂太慢（{settle_ms:.0f}ms）"
    else:
        note = ""

    print(f"  {'ok  ' if ok else 'FAIL'} {label}: 過衝 {overshoot_pct:+.1f}%　收斂 {settle_ms:.0f}ms  {note}")
    if not ok:
        fails.append(label)


print("\n彈簧參數驗證")
run("展開 (0.40, 0.70)", 0.40, 0.70, True)
run("收合 (0.52, 1.00)", 0.52, 1.00, False)
run("現身 (0.46, 0.72)", 0.46, 0.72, True)
run("隱藏 (0.36, 1.00)", 0.36, 1.00, False)
run("內容 (0.34, 1.00)", 0.34, 1.00, False)

print("\n中途改目標（被打斷）：位置要連續，且仍能收斂到新目標")
s = isl.Spring(0.0, 0.40, 0.70)
s.target = 1.0
for _ in range(12):
    s.step(DT)
mid, vel = s.value, s.velocity
s.target = 0.35
s.step(DT)

# 位置只能靠速度積分改變，不能有不連續的跳躍。
# 速度本身可以劇烈改變——目標往反方向移了 0.63，加速度大是彈簧的正確行為。
jump = abs(s.value - mid)
expected = abs(vel) * DT
continuous = abs(jump - expected) < 0.01
print(f"  {'ok  ' if continuous else 'FAIL'} 位置連續：實際位移 {jump:.4f}，速度積分預期 {expected:.4f}")
if not continuous:
    fails.append("interrupt-continuity")

for i in range(600):
    s.step(DT)
    if s.settled:
        break
converged = s.settled and abs(s.value - 0.35) < 0.01
print(f"  {'ok  ' if converged else 'FAIL'} 打斷後仍收斂到 0.35：停在 {s.value:.4f}（{(i + 1) * DT * 1000:.0f}ms）")
if not converged:
    fails.append("interrupt-converge")

print("\n掉幀保護（dt=0.5s）不該爆炸")
s = isl.Spring(0.0, 0.40, 0.70)
s.target = 1.0
s.step(0.5)
ok = abs(s.value) < 2.0
print(f"  {'ok  ' if ok else 'FAIL'} 大 dt 後的值 {s.value:.3f}")
if not ok:
    fails.append("dt clamp")

print("\n" + ("全部通過" if not fails else f"有 {len(fails)} 項失敗：{fails}"))
sys.exit(1 if fails else 0)

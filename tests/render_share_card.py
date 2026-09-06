# -*- coding: utf-8 -*-
"""渲染分享卡片，存成 PNG 供目視確認。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import stats_window as sw  # noqa: E402
import island as isl  # noqa: E402

from PySide6.QtWidgets import QApplication  # noqa: E402

EVENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wp_dash", "events.jsonl")
if not os.path.exists(EVENTS):
    raise SystemExit("先跑 gen_dashboard.py 產資料")

app = QApplication(sys.argv)

import dashboard  # noqa: E402
cfg = dict(isl.DEFAULT_CONFIG)
d = dashboard.compute(cfg, EVENTS)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
fails = []

# --- streak=12 ---
d["streak"]["streak"] = 12
d["streak"]["saves_left"] = 1
d["longest"] = max(d["longest"], 12)
d["today"]["drinks"] = 5

pix = sw.render_share_card(d)
out = os.path.join(OUT_DIR, "share_card.png")
pix.save(out)
print(f"streak=12 -> {out}  {pix.width()}x{pix.height()}")
if pix.width() != 1080 or pix.height() != 1080:
    fails.append(f"streak=12: expected 1080x1080, got {pix.width()}x{pix.height()}")

# --- streak=0 ---
d["streak"]["streak"] = 0
d["streak"]["saves_left"] = 0
d["longest"] = 0
d["today"]["drinks"] = 0

pix0 = sw.render_share_card(d)
out0 = os.path.join(OUT_DIR, "share_card_zero.png")
pix0.save(out0)
print(f"streak=0  -> {out0}  {pix0.width()}x{pix0.height()}")
if pix0.width() != 1080 or pix0.height() != 1080:
    fails.append(f"streak=0: expected 1080x1080, got {pix0.width()}x{pix0.height()}")

if fails:
    for f in fails:
        print(f"FAIL: {f}")
    sys.exit(1)
print("OK")
sys.exit(0)

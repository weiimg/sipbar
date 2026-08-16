# -*- coding: utf-8 -*-
"""用真的游標位置測頂端探頭，不 mock 任何東西。"""
import ctypes
import os
import shutil
import sys
import time

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import island as isl  # noqa: E402

TEST_DIR = os.path.join(SCRATCH, "wp_peeklive")
shutil.rmtree(TEST_DIR, ignore_errors=True)
isl.DATA_DIR = TEST_DIR
isl.STATE_PATH = os.path.join(TEST_DIR, "state.json")
isl.EVENTS_PATH = os.path.join(TEST_DIR, "events.jsonl")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
w = isl.Island(dict(isl.DEFAULT_CONFIG))
w.tick_timer.stop()

scr = QApplication.primaryScreen().geometry()
# 測熱區邊緣而不是正中心：能打到邊緣才代表實務上摸得到
target_x = scr.center().x() + isl.peek_half_w(scr.width(), QApplication.primaryScreen().devicePixelRatio()) - 20
target_y = scr.top() + isl.PEEK_EDGE_PX - 2
print(f"螢幕 {scr.width()}x{scr.height()} top={scr.top()} center.x={scr.center().x()}")
print(f"熱區 x in [{scr.center().x() - isl.peek_half_w(scr.width(), QApplication.primaryScreen().devicePixelRatio())}, {scr.center().x() + isl.peek_half_w(scr.width(), QApplication.primaryScreen().devicePixelRatio())}]  y<={scr.top() + isl.PEEK_EDGE_PX}")

saved = isl.cursor_pos()
ctypes.windll.user32.SetCursorPos(target_x, target_y)
time.sleep(0.15)
print("移動後實際游標:", isl.cursor_pos(), " <- Windows 有沒有讓它停在那")

results = {}


def phase1():
    # 這個測試會搶走真實游標。使用者同時在用滑鼠時游標會被移走，
    # 那是干擾不是失敗——先確認游標還在熱區，不在就標記略過。
    x, y = isl.cursor_pos()
    in_zone = abs(x - scr.center().x()) <= isl.peek_half_w(scr.width(), QApplication.primaryScreen().devicePixelRatio()) and y <= scr.top() + isl.PEEK_EDGE_PX
    if not in_zone:
        results["skipped"] = f"游標被移到 ({x}, {y})，不在熱區"
    w._peek_tick()
    results["peeking"] = w._peeking
    results["reveal_target"] = w.sp_reveal.target


def phase2():
    results["visible"] = w.isVisible()
    results["reveal_value"] = round(w.sp_reveal.value, 3)
    results["pill_top"] = round(w.pill_rect().top(), 1)
    ctypes.windll.user32.SetCursorPos(saved[0], saved[1])
    app.quit()


QTimer.singleShot(100, phase1)
QTimer.singleShot(1400, phase2)
app.exec()

print("\n--- 結果 ---")
for k, v in results.items():
    print(f"  {k} = {v}")

if results.get("skipped"):
    print(f"\n略過：{results['skipped']}（你正在用滑鼠，不是程式的問題）")
    sys.exit(0)

ok = results.get("peeking") and results.get("visible") and results.get("reveal_value", 0) > 0.9
print("\n" + ("探頭正常運作" if ok else "探頭沒有生效"))
sys.exit(0 if ok else 1)

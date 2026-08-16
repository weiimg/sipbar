# -*- coding: utf-8 -*-
"""產生 README 的展示動畫 —— docs/demo.webp。

演的是 onboard.py 的 IslandPreview：一台縮小的桌面，島從螢幕上緣滑下來、
游標點一下、變成已記錄、滑回去。那支 widget 本來就是為了「不用文字解釋
位置關係」而畫的，README 要的正是同一件事，所以不另外畫一套。

## 為什麼是 WebP 不是 GIF

畫面下緣是羽化掉的（IslandPreview.FADE_H），alpha 從 255 平滑降到 0。
GIF 的透明是二值的——不是全透就是全不透，羽化會變成一圈鋸齒或一塊白底，
而 README 在 GitHub 的淺色與深色主題下都要看得對。
WebP 有真 alpha，兩個主題都乾淨，順便小一半以上。

## 為什麼先空跑一圈

彈簧是有狀態的。從 t=0、速度 0 開始錄，第一圈的落點會比穩態淺一點，
接回開頭就會看到跳動。先跑滿一個 T_LOOP 讓它進入穩態，錄第二圈，
首尾才接得起來。

用法：python tools/make_demo.py
"""
import os
import sys

from PIL import Image
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import onboard  # noqa: E402
import typeface  # noqa: E402

OUT = os.path.join(ROOT, "docs", "demo.webp")

# 25fps 是實測的下限。20fps 時島滑下來那段（0.3-1.2 秒，彈簧最快的一段）
# 看得出來在跳格；30fps 沒有比 25 好看，只是多 15 張圖。
FPS = 25


def frames():
    """跑滿兩圈，回傳第二圈的每一幀。"""
    w = onboard.IslandPreview(interactive=False)
    w.resize(w.W, w.H)
    n = int(round(w.T_LOOP * FPS))
    dt = 1.0 / FPS

    for _ in range(n):
        w.step(dt)

    out = []
    for _ in range(n):
        w.step(dt)
        img = w.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
        out.append(Image.frombytes(
            "RGBA", (img.width(), img.height()), img.constBits().tobytes()))
    return out


def main():
    app = QApplication.instance() or QApplication(sys.argv)   # noqa: F841
    ok, why = typeface.ensure_loaded()
    if not ok:
        # 字體沒載到就會用系統字，錄出來的圖跟實際畫面不一樣——那比錄不出來更糟，
        # 因為它會靜默地產出一張看起來沒問題、但字重與字距都不對的圖。
        print(f"FAIL 字體沒載起來：{why}")
        return 1

    fs = frames()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fs[0].save(OUT, format="WEBP", save_all=True, append_images=fs[1:],
               duration=int(round(1000 / FPS)), loop=0, lossless=False,
               quality=88, method=6)

    kb = os.path.getsize(OUT) / 1024
    print(f"{OUT}")
    print(f"  {fs[0].width}x{fs[0].height}  {len(fs)} 幀  {FPS}fps  {kb:.0f}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

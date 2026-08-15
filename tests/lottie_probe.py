# -*- coding: utf-8 -*-
"""Lottie 素材探測：耗時、alpha、水位曲線、膠捲圖。

Phase 0 用它做可行性判斷，Phase 1 用它篩素材——判準不是「動畫好不好看」，
是「停在中間某一幀好不好讀」，所以一定要把中間幀畫出來用眼睛看。

用法：
    python lottie_probe.py <a.json> [b.json ...]

每個素材輸出一張 <名稱>_strip.png，是疊在藥丸底色上的五個狀態位置。
"""
import os
import statistics
import sys
import time

from PIL import Image, ImageDraw, ImageFont
from rlottie_python import LottieAnimation

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
PILL_BG = (22, 23, 27)           # island.py 藥丸漸層的中間值
SIZES = [("展開 60px", 60), ("收合 22px", 22)]
# 規劃第十六節的狀態對應。注意這是「時間軸位置」，不保證等於水位——見 level_curve()
STATES = [("正常", 0.00), ("中段", 0.30), ("口渴", 0.60), ("虛弱", 0.85), ("倒地", 1.00)]
BUDGET_MS = 10.0                 # Phase 0 判準


def load(path):
    """一律用 from_data，不要用 from_file。

    from_file() 把路徑交給 rlottie 的 C API，路徑含非 ASCII 字元時會**靜默失敗**：
    不丟例外，回一個 0 幀 0x0 的空動畫。本專案就住在「喝水提醒桌寵」裡，
    from_file() 在這裡永遠載不起來。

    連帶的重點：規劃寫「載入失敗一律 fallback 回幾何臉」，但靜默失敗不會觸發
    try/except——**fallback 的判斷必須是 totalframe() > 0，不是接例外。**
    """
    with open(path, "r", encoding="utf-8") as f:
        anim = LottieAnimation.from_data(f.read())
    if anim.lottie_animation_get_totalframe() <= 0:
        raise ValueError(f"載入後 0 幀，這個 Lottie 有問題：{path}")
    return anim


def frames(anim):
    return anim.lottie_animation_get_totalframe()


def bench(anim, size, n=60):
    total = frames(anim)
    times = []
    for i in range(n):
        f = int(i * total / n)
        t0 = time.perf_counter()
        anim.lottie_animation_render(frame_num=f, width=size, height=size)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    return statistics.median(times), times[int(len(times) * 0.95)]


def alpha_report(anim, size=60):
    """rlottie 輸出 premultiplied BGRA。三件事要對：
    透明區必須是純 0（否則疊上去有色暈）、要有半透明邊緣（否則沒抗鋸齒）、
    max(RGB) <= A（premultiplied 的定義，決定 Qt 要用哪個 Format）。
    """
    img = anim.render_pillow_frame(frame_num=0, width=size, height=size)
    px = list(img.getdata())
    clear = [p for p in px if p[3] == 0]
    edge = [p for p in px if 0 < p[3] < 255]
    return {
        "最大 alpha": max(p[3] for p in px),
        "半透明邊緣": len(edge),
        "透明區有殘色": sum(1 for p in clear if p[:3] != (0, 0, 0)),
        "違反 premultiplied": sum(1 for p in px if p[3] < 255 and max(p[:3]) > p[3] + 1),
    }


def level_curve(anim, size=60):
    """量每一幀的「覆蓋面積」當水位代理值，正規化到 0..1。

    規劃的狀態表把時間軸位置直接當水位用，但那只有素材是線性的時候才成立。
    實測用自製素材差到 21 個百分點，所以這張表要量出來，不能算出來。
    """
    total = frames(anim)
    cov = []
    for f in range(total):
        img = anim.render_pillow_frame(frame_num=f, width=size, height=size)
        a = img.getchannel("A").histogram()
        cov.append(sum(a[128:]))
    lo, hi = min(cov), max(cov)
    span = max(1, hi - lo)
    return [(c - lo) / span for c in cov]


def label_font(px=15):
    """PIL 預設是點陣字型，不含中文，標籤會變方塊。膠捲圖是拿來比較素材的，
    標籤看不懂就失去意義——沿用島用的 Noto Sans TC。"""
    for p in (os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts\NotoSansTC-Medium.otf"),
              r"C:\Windows\Fonts\NotoSansTC-VF.ttf",
              r"C:\Windows\Fonts\msjh.ttc"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, px)
            except OSError:
                continue
    return ImageFont.load_default()


def composite(img, scale):
    """premultiplied over：dst = src + dst*(1-a)。
    直接丟給 PIL 的 alpha_composite 會當成直通道，邊緣會偏亮。
    """
    out = Image.new("RGB", img.size, PILL_BG)
    src, dst = img.load(), out.load()
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            sr, sg, sb, sa = src[x, y]
            dr, dg, db = dst[x, y]
            inv = (255 - sa) / 255.0
            dst[x, y] = (int(sr + dr * inv), int(sg + dg * inv), int(sb + db * inv))
    return out.resize((img.size[0] * scale, img.size[1] * scale), Image.NEAREST)


def strip(anim, name, cell=60, scale=4):
    total = frames(anim)
    pad = 14
    w = pad + len(STATES) * (cell * scale + pad)
    canvas = Image.new("RGB", (w, pad * 2 + cell * scale + 24), PILL_BG)
    d = ImageDraw.Draw(canvas)
    font = label_font()
    for i, (label, pos) in enumerate(STATES):
        f = min(total - 1, int(round(pos * (total - 1))))
        img = anim.render_pillow_frame(frame_num=f, width=cell, height=cell)
        x = pad + i * (cell * scale + pad)
        canvas.paste(composite(img, scale), (x, pad))
        d.text((x + 4, pad + cell * scale + 5), f"{label}　{pos*100:.0f}%　第 {f} 幀",
               font=font, fill=(226, 226, 232))
    path = os.path.join(OUT_DIR, f"{name}_strip.png")
    canvas.save(path)
    return path


def probe(path):
    name = os.path.splitext(os.path.basename(path))[0]
    anim = load(path)
    w, h = anim.lottie_animation_get_size()
    print(f"\n{'=' * 66}\n{name}")
    print(f"  {w}x{h}　{frames(anim)} 幀　{anim.lottie_animation_get_framerate():.0f}fps　"
          f"{anim.lottie_animation_get_duration():.2f}s　檔案 {os.path.getsize(path)/1024:.1f}KB")

    print("\n  單幀耗時")
    worst = 0.0
    for label, size in SIZES:
        med, p95 = bench(anim, size)
        worst = max(worst, p95)
        print(f"    {'ok  ' if p95 < BUDGET_MS else 'FAIL'}  {label:<10} "
              f"中位 {med:.3f}ms　p95 {p95:.3f}ms")

    print("\n  alpha")
    for k, val in alpha_report(anim).items():
        print(f"    {k}：{val}")

    print("\n  時間軸位置 vs 實際水位")
    lv = level_curve(anim)
    total = frames(anim)
    worst_err = 0.0
    for label, pos in STATES:
        f = min(total - 1, int(round(pos * (total - 1))))
        assumed = 1.0 - pos
        err = abs(lv[f] - assumed)
        worst_err = max(worst_err, err)
        print(f"    {label:<4} 時間軸 {pos*100:>3.0f}%　實際 {lv[f]*100:>3.0f}%　"
              f"線性假設 {assumed*100:>3.0f}%　誤差 {err*100:>3.0f}pp")
    if worst_err > 0.15:
        print(f"    -> 誤差 {worst_err*100:.0f}pp，非線性。要用量出來的「水位 -> 幀」對照表")
    print("    水位 -> 幀：", "　".join(
        f"{int(want*100)}%→f{min(range(total), key=lambda i: abs(lv[i] - want))}"
        for want in (1.0, 0.75, 0.5, 0.25, 0.0)))

    print(f"\n  膠捲圖：{strip(anim, name)}")
    return worst


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("用法：python lottie_probe.py <lottie.json> [...]")
        sys.exit(2)
    worst = max(probe(p) for p in args)
    ok = worst < BUDGET_MS
    print(f"\n{'=' * 66}")
    print(f"判準：單幀 p95 最差 {worst:.3f}ms {'<' if ok else '>='} {BUDGET_MS}ms"
          f" -> {'通過' if ok else '未通過'}")
    sys.exit(0 if ok else 1)

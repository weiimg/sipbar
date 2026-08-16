# -*- coding: utf-8 -*-
"""產生社群用的示意動畫 —— docs/social-laptop.gif 與 .webp。

畫的是一台完整的筆電，背景透明，島從螢幕上緣滑下來、游標點一下、走掉。
給社群貼文用，可以直接疊在任何底色上。

## 島是正版的，不是重畫的

裡面的島是真的 `island.Island` 這個 widget 逐幀 grab 出來的——同一份
paintEvent、同一組彈簧參數、同一顆像素杯。重畫一套「看起來很像」的島，
只要正式版改了樣子，宣傳圖就會開始說謊。

資料路徑在建構之前就被導到暫存資料夾，`settings.guard_real_write` 會擋住
任何寫到真實紀錄的嘗試——錄影不能污染使用者的資料。

## 為什麼用固定 dt 而不是呼叫 _step()

`Island._step()` 讀 `time.perf_counter()` 算時間差。在錄影迴圈裡連續呼叫，
每次的 dt 都趨近 0，彈簧根本不會動。錄影要的是決定性的結果，所以直接用
固定 dt 推進彈簧。

## GIF 與 WebP 都出，因為 GIF 的透明是二值的

GIF 每個像素只能全透或全不透，筆電的圓角與陰影邊緣會有鋸齒。WebP 有真
alpha，同樣的內容乾淨得多。兩個都存，要哪個自己挑。

用法：python tools/make_social_demo.py
"""
import os
import sys
import tempfile

from PIL import Image
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen)
from PySide6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

# 沙箱要在 import island 之後、建構 Island 之前就位。
import island as isl  # noqa: E402

SANDBOX = tempfile.mkdtemp(prefix="sipbar_social_")
isl.DATA_DIR = SANDBOX
isl.EVENTS_PATH = os.path.join(SANDBOX, "events.jsonl")
isl.STATE_PATH = os.path.join(SANDBOX, "state.json")

import onboard  # noqa: E402
import settings  # noqa: E402
import typeface  # noqa: E402

OUT_GIF = os.path.join(ROOT, "docs", "social-laptop.gif")
OUT_WEBP = os.path.join(ROOT, "docs", "social-laptop.webp")

FPS = 25

# 畫布。筆電置中，四周留一點空間讓陰影不被切掉。
W, H = 1000, 720

# 筆電。螢幕是 16:10，底座往兩側外擴——那是筆電從正面看的樣子。
LID_W, LID_H = 860, 538
BEZEL = 14                      # 螢幕黑框
LID_R = 18                      # 上蓋圓角
BASE_H = 26                     # 底座厚度
BASE_OVERHANG = 52              # 底座比上蓋往外多出來的寬度
HINGE_GAP = 3

LID_X = (W - LID_W) // 2
LID_Y = 62
SCR_X, SCR_Y = LID_X + BEZEL, LID_Y + BEZEL
SCR_W, SCR_H = LID_W - BEZEL * 2, LID_H - BEZEL * 2

# 影片裡的島不展開訊息文字。
#
# 收合成小藥丸是島真實的狀態之一（USAGE.md：「縮成小藥丸但不消失」），不是
# 假的畫面。不放字的理由：中文字在社群的播放尺寸下只剩幾個像素高，讀不到卻
# 佔掉三倍寬度，把杯子和進度點擠小——而那兩樣才是這支要給人看的東西。
# README 那支 docs/demo.webp 也是同一個取捨。
SHOW_MESSAGE = False

# 島縮放。這是整支影片唯一需要憑眼睛調的數字，改它就好，不要動別的。
#
# 對齊 README 那支 demo 的比例：onboard.IslandPreview 的 PILL_MAX_W = 110，
# 螢幕寬 448px，藥丸佔 24.5%。兩支放在一起才像同一個產品。
ISLAND_SCALE = 1.39

# 時間軸。死時間要少，社群上前兩秒沒東西發生就滑掉了。
T_START = 0.4                   # 空畫面，讓人看清楚它平常不存在
T_CURSOR = 1.5                  # 游標開始往島移動
T_CLICK = 2.5                   # 點下去
T_LEAVE = 3.6                   # 島開始滑走
T_LOOP = 4.6

SPRINGS = ("sp_expand", "sp_reveal", "sp_content", "sp_pulse", "sp_level")


# ---------------------------------------------------------------- 筆電

_WALL = None


def wallpaper():
    """用正版的像素桌布，不要自己另外調一張。

    `IslandPreview._build_wallpaper` 的註解講得很清楚：螢幕裡站的是一隻像素
    杯子，桌布用照片或平滑漸層就變成兩種畫風貼在一起。這裡曾經自己編過一張
    藍色漸層，正好就是它警告的那件事。

    先照 preview 的原始尺寸畫再放大，不要直接用全尺寸畫：雲的位置寫死在格子
    座標裡（是手排的，不是亂數），畫布一寬，三團雲就會全部擠到左邊。
    放大用最近鄰，像素邊緣才不會被抹糊——而且格子變大，社群上更讀得出來。
    """
    global _WALL
    if _WALL is None:
        small = onboard.IslandPreview._build_wallpaper(SCR_W // 2, SCR_H // 2)
        _WALL = small.scaled(SCR_W, SCR_H, Qt.IgnoreAspectRatio,
                             Qt.FastTransformation)
    return _WALL


def draw_wallpaper(p):
    path = QPainterPath()
    path.addRoundedRect(QRectF(SCR_X, SCR_Y, SCR_W, SCR_H), 7, 7)
    p.save()
    p.setClipPath(path)
    p.drawPixmap(SCR_X, SCR_Y, wallpaper())
    p.restore()


def draw_laptop_body(p):
    """上蓋、黑框、底座。底座畫成上窄下寬的梯形，那是正面看筆電的樣子。"""
    # 上蓋外殼
    lid = QRectF(LID_X, LID_Y, LID_W, LID_H)
    shell = QPainterPath()
    shell.addRoundedRect(lid, LID_R, LID_R)
    g = QLinearGradient(lid.topLeft(), lid.bottomLeft())
    g.setColorAt(0.0, QColor("#3A3D45"))
    g.setColorAt(1.0, QColor("#24262B"))
    p.fillPath(shell, g)

    # 外殼邊緣的一道亮邊，金屬感就靠這條
    p.setPen(QPen(QColor(255, 255, 255, 34), 1.4))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(lid.adjusted(0.7, 0.7, -0.7, -0.7), LID_R, LID_R)

    # 底座：上緣貼著上蓋，下緣往兩側外擴
    top_y = LID_Y + LID_H + HINGE_GAP
    bot_y = top_y + BASE_H
    base = QPainterPath()
    base.moveTo(LID_X - 2, top_y)
    base.lineTo(LID_X + LID_W + 2, top_y)
    base.lineTo(LID_X + LID_W + BASE_OVERHANG, bot_y - 7)
    base.quadTo(LID_X + LID_W + BASE_OVERHANG, bot_y,
                LID_X + LID_W + BASE_OVERHANG - 12, bot_y)
    base.lineTo(LID_X - BASE_OVERHANG + 12, bot_y)
    base.quadTo(LID_X - BASE_OVERHANG, bot_y, LID_X - BASE_OVERHANG, bot_y - 7)
    base.closeSubpath()
    bg = QLinearGradient(0, top_y, 0, bot_y)
    bg.setColorAt(0.0, QColor("#2C2F35"))
    bg.setColorAt(1.0, QColor("#43464E"))
    p.fillPath(base, bg)

    # 開闔用的凹槽
    notch = QRectF(W / 2 - 54, bot_y - BASE_H, 108, 7)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 70))
    p.drawRoundedRect(notch, 3.5, 3.5)


def draw_cursor(p, x, y, pressed):
    """標準的箭頭游標。按下去時縮一點，那一下的回饋比什麼都清楚。"""
    s = 0.9 if pressed else 1.0
    p.save()
    p.translate(x, y)
    p.scale(s, s)
    arrow = QPainterPath()
    arrow.moveTo(0, 0)
    arrow.lineTo(0, 25)
    arrow.lineTo(6.4, 19.2)
    arrow.lineTo(10.6, 28.4)
    arrow.lineTo(15.2, 26.2)
    arrow.lineTo(11.0, 17.4)
    arrow.lineTo(19.2, 17.0)
    arrow.closeSubpath()
    p.setPen(QPen(QColor(20, 20, 24, 190), 2.6))
    p.setBrush(QColor(255, 255, 255))
    p.drawPath(arrow)

    if pressed:                       # 點擊的漣漪
        p.setPen(QPen(QColor(255, 255, 255, 120), 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(1, 1), 15, 15)
    p.restore()


# ---------------------------------------------------------------- 島

def advance(w, dt, clock):
    """用固定 dt 推進彈簧。不走 _step()，理由見檔案開頭。

    順便手動補上 `_content_delay` 那顆 QTimer。`_enter()` 是這樣叫的：

        self._target_content(1.0, delay_ms=90)   # 容器先動，字後到

    沒有跑 Qt 事件迴圈的話那一發永遠不開火，`sp_content` 卡在 0，
    島從頭到尾不展開文字——藥丸就比真正的島窄一截，宣傳圖會說謊。
    """
    if not SHOW_MESSAGE:
        w._content_delay.stop()
        w.sp_content.target = w.sp_content.value = 0.0
        w.sp_content.velocity = 0.0
    elif w._content_delay.isActive():
        if clock.get("content_due") is None:
            clock["content_due"] = w._content_delay.interval() / 1000.0
        clock["content_due"] -= dt
        if clock["content_due"] <= 0:
            w._content_delay.stop()
            w._apply_pending_content()
            clock["content_due"] = None
    else:
        clock["content_due"] = None

    for name in SPRINGS:
        getattr(w, name).step(dt)
    w._apply_mask()


def island_frame(w):
    return w.grab().toImage().convertToFormat(QImage.Format_RGBA8888)


# ---------------------------------------------------------------- 主流程

def frames(w):
    n = int(round(T_LOOP * FPS))
    dt = 1.0 / FPS
    out = []

    # 島從畫面外開始
    w._enter(isl.NORMAL, animate=False)
    for name in SPRINGS:
        s = getattr(w, name)
        s.value = s.target = 0.0
        s.velocity = 0.0

    entered = clicked = leaving = False
    clock = {"content_due": None}
    widest = 0.0
    cursor_from = QPointF(SCR_X + SCR_W * 0.78, SCR_Y + SCR_H * 0.74)
    cursor_to = QPointF(W / 2 + 16, SCR_Y + 46 * ISLAND_SCALE + 22)

    for i in range(n):
        t = i * dt

        if not entered and t >= T_START:
            w._enter(isl.THIRSTY, animate=True)
            entered = True
        if not clicked and t >= T_CLICK:
            w.drink()                       # 正版的補水流程：杯子變綠、進度多一格
            clicked = True
        if not leaving and t >= T_LEAVE:
            w._target_reveal(0.0)
            w._target_expand(0.0)
            leaving = True

        advance(w, dt, clock)
        widest = max(widest, w.pill_rect().width())

        canvas = QImage(W, H, QImage.Format_RGBA8888)
        canvas.fill(Qt.transparent)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        draw_laptop_body(p)
        draw_wallpaper(p)

        # 島疊在螢幕上，超出螢幕的部分裁掉——它是從螢幕上緣滑進來的
        isle = island_frame(w)
        iw = int(isle.width() * ISLAND_SCALE)
        ih = int(isle.height() * ISLAND_SCALE)
        scaled = isle.scaled(iw, ih, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(SCR_X, SCR_Y, SCR_W, SCR_H), 7, 7)
        p.save()
        p.setClipPath(clip)
        p.drawImage(int(W / 2 - iw / 2), SCR_Y, scaled)
        p.restore()

        if t >= T_CURSOR:
            k = min(1.0, (t - T_CURSOR) / max(0.001, T_CLICK - T_CURSOR))
            k = k * k * (3 - 2 * k)             # smoothstep，機械式等速最假
            cx = cursor_from.x() + (cursor_to.x() - cursor_from.x()) * k
            cy = cursor_from.y() + (cursor_to.y() - cursor_from.y()) * k
            if t < T_LEAVE + 0.2:
                draw_cursor(p, cx, cy, T_CLICK <= t < T_CLICK + 0.24)

        p.end()
        out.append(Image.frombytes(
            "RGBA", (canvas.width(), canvas.height()),
            canvas.constBits().tobytes()))
    print(f"藥丸最寬 {widest:.0f}px（原尺寸）→ 畫面上 {widest * ISLAND_SCALE:.0f}px"
          f"，佔螢幕寬 {widest * ISLAND_SCALE / SCR_W * 100:.0f}%")
    return out


def save_gif(fs, path):
    """GIF 的透明是二值的，所以要自己做調色盤：留一格給全透明，其餘量化。

    直接 convert("P") 會把 alpha 丟掉，半透明的圓角與陰影會變成一圈黑邊。
    """
    conv = []
    for f in fs:
        alpha = f.getchannel("A")
        # 255 色給畫面，第 256 格留給透明
        q = f.convert("RGB").quantize(colors=255, method=Image.MEDIANCUT)
        mask = alpha.point(lambda a: 255 if a <= 128 else 0)
        q.paste(255, mask)
        q.info["transparency"] = 255
        conv.append(q)
    conv[0].save(path, save_all=True, append_images=conv[1:],
                 duration=int(round(1000 / FPS)), loop=0,
                 transparency=255, disposal=2, optimize=False)


def main():
    app = QApplication.instance() or QApplication(sys.argv)   # noqa: F841
    ok, why = typeface.ensure_loaded()
    if not ok:
        # 字體沒載到就會用系統字，錄出來跟實際畫面不一樣——那比錄不出來更糟，
        # 因為它會靜默產出一張看起來沒問題、但字重與字距都不對的圖。
        print(f"FAIL 字體沒載起來：{why}")
        return 1

    cfg = dict(settings.DEFAULTS)
    cfg.update(daily_target_drinks=7, face_style="pixel", theme="dark")
    w = isl.Island(cfg)
    w.drinks = 3                       # 進度點有幾格已經亮著，點下去才看得出多一格

    fs = frames(w)
    os.makedirs(os.path.dirname(OUT_GIF), exist_ok=True)

    fs[0].save(OUT_WEBP, format="WEBP", save_all=True, append_images=fs[1:],
               duration=int(round(1000 / FPS)), loop=0, lossless=False,
               quality=90, method=6)
    save_gif(fs, OUT_GIF)

    for path in (OUT_WEBP, OUT_GIF):
        print(f"{path}")
        print(f"  {fs[0].width}x{fs[0].height}  {len(fs)} 幀  {FPS}fps  "
              f"{os.path.getsize(path) / 1024:.0f}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())

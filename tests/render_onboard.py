# -*- coding: utf-8 -*-
"""引導的每一頁定格，深淺兩套。

各頁高度**不一樣**是刻意的：內容多少就多高，視窗用彈簧補間過去。
所以這支不是檢查「三頁同高」，而是檢查兩件相反的事：

1. 停下來的時候，每一頁都剛好包住自己的內容——不能有大片空白（讀起來像沒做完），
   也不能切到按鈕（那就真的壞了）。
2. 補間的中途不能把內容壓扁。頁面是自然高度、由容器裁切，所以中途只會少露出
   一截，不會有任何東西被擠小。
"""
import os
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"E:\Claude Project\Claude Inbox\喝水提醒桌寵")

import onboard  # noqa: E402
import stats_window as sw  # noqa: E402

from PySide6.QtGui import QColor, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

fails = []


def check(ok, label, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{'　' + detail if detail else ''}")
    if not ok:
        fails.append(label)


def shot_flow(theme_name):
    print(f"\n{theme_name}")
    sw.apply_theme(theme_name)
    sw._FONTS.clear()
    win = onboard.OnboardWindow()
    win.show()
    win.setWindowOpacity(1.0)
    win.sp_win.snap(1.0)
    app.processEvents()

    frames = []
    # 跟著實際頁數走，不寫死 3。加第四頁時就是靠這行自動納入檢查。
    for i in range(len(win.deck.pages)):
        win._go(i)
        win.sp_h.snap()
        win._apply_height()
        if i == 2:
            t = 0.0
            while t < 1.0:          # 停在「島已經滑下來」那一格
                win.preview.step(1 / 60)
                t += 1 / 60
        app.processEvents()

        page = win.deck.pages[i]
        # 停下來時視窗要剛好包住這一頁：多了是空白，少了是切到按鈕。
        check(win.height() - onboard.CHROME == page.height(),
              f"第 {i + 1} 頁停下來時剛好包住內容",
              f"視窗內容區 {win.height() - onboard.CHROME}px / 頁面 {page.height()}px")
        # 按鈕是每一頁的最後一列，被切到就等於這一頁無法完成。
        actions = page.layout().itemAt(page.layout().count() - 1).widget()
        check(actions.geometry().bottom() <= page.height(),
              f"第 {i + 1} 頁的按鈕沒有被裁掉",
              f"按鈕底部 {actions.geometry().bottom()} / 可視 {page.height()}")
        frames.append(win.grab())

    # 補間中途：把高度停在一半，頁面的內部尺寸不能跟著縮。
    win._go(0)
    win._h_from, win._h_to = win.deck.natural(2), win.deck.natural(0)
    win.deck.show_page(2)
    before = [w.size() for w in win.deck.pages[2].findChildren(type(win.preview))]
    win.sp_h.value = 0.5
    win._apply_height()
    app.processEvents()
    after = [w.size() for w in win.deck.pages[2].findChildren(type(win.preview))]
    check(before == after and before, "補間中途沒有壓扁內容",
          f"預覽尺寸 {before[0].width()}x{before[0].height()}" if before else "")

    print(f"  各頁高度 {[f.height() for f in frames]}")
    return frames


def check_clipping():
    """滑入時藥丸必須被螢幕上緣裁掉，不能畫到外框那一圈上面。

    整張示意圖的意思就靠這一段：**它是從螢幕外面滑進來的。** 沒有裁切的話
    藥丸會浮在外框上，看起來像貼在圖上面的標籤，位置關係就沒說到。
    這也是為什麼不再需要「螢幕上緣」那行小字——需要旁白的示意圖等於沒說清楚。

    **不比顏色。** 外框（22,24,28）跟藥丸（30,31,36 -> 14,15,18）幾乎同色，
    用色差判斷會漏。改成比「藥丸還沒出現」與「滑到一半」兩張圖的外框那條帶：
    只要有一個像素不同，就是漏出去了。
    """
    print("")
    print("裁切（藥丸不能畫到螢幕外框上）")
    sw.apply_theme("light")
    sw._FONTS.clear()
    pv = onboard.IslandPreview()
    pv.reveal = 1.0
    pv.resize(pv.W, pv.H)

    def band():
        pm = QPixmap(pv.W, pv.H)
        pm.fill(sw.PAL.card_top)
        pv.render(pm)
        img = pm.toImage()
        return [img.pixelColor(x, y).rgba()
                for y in range(pv.BEZEL)
                for x in range(pv.W // 2 - 90, pv.W // 2 + 90)]

    pv.sp_drop.snap(0.0)
    pv.sp_open.snap(0.0)
    baseline = band()

    worst, t = 0, 0.0
    while t < 1.2:
        pv.step(1 / 60)
        t += 1 / 60
        worst = max(worst, sum(1 for a, b in zip(baseline, band()) if a != b))
    check(worst == 0, "滑入全程外框都沒有被藥丸蓋到", f"不同的像素 {worst} 個")


def check_transition():
    """走一次真的補間，逐格檢查視窗幾何。

    定格圖看不出這一段：中途只要有一格倒退或超出螢幕，看起來就是抖一下。
    """
    print("\n補間（第 1 頁 -> 第 3 頁，最大的一次長高）")
    sw.apply_theme("dark")
    win = onboard.OnboardWindow()
    scr = QApplication.primaryScreen().availableGeometry()
    win.move(scr.center().x() - win.width() // 2,
             scr.center().y() - win.height() // 2)
    win.anchor_here()
    win.show()
    win.sp_win.snap(1.0)
    app.processEvents()

    anchor = win._anchor_y
    win._go(2)
    heights, tops = [win.height()], [win.y()]
    for _ in range(240):                      # 4 秒上限，收斂不了就抓得到
        win.sp_h.step(1 / 60)
        win._apply_height()
        heights.append(win.height())
        tops.append(win.y())
        if win.sp_h.settled:
            break

    check(all(b >= a for a, b in zip(heights, heights[1:])),
          "高度全程不倒退", f"{heights[0]} -> {heights[-1]}px，{len(heights)} 格")
    check(win.sp_h.settled, "有收斂", f"{len(heights) / 60:.2f} 秒")
    check(heights[-1] == win.deck.natural(2) + onboard.CHROME,
          "停在第 3 頁的自然高度", f"{heights[-1]}px")
    check(all(t >= scr.top() and t + h <= scr.bottom()
              for t, h in zip(tops, heights)),
          "全程沒有掉出螢幕", f"上緣 {min(tops)} 下緣 {max(t + h for t, h in zip(tops, heights))}")
    centers = {t + h // 2 for t, h in zip(tops, heights)}
    check(max(abs(c - anchor) for c in centers) <= 1,
          "中心線鎖住，往兩邊長", f"偏移 {max(abs(c - anchor) for c in centers):.0f}px")


rows = [shot_flow("light"), shot_flow("dark")]
check_clipping()
check_transition()
pad = 18
w = max(f.width() for r in rows for f in r)
h = max(f.height() for r in rows for f in r)
cols = max(len(r) for r in rows)
sheet = QPixmap(pad + (w + pad) * cols, pad + (h + pad) * len(rows))
sheet.fill(QColor("#8A8D95"))
p = QPainter(sheet)
y = pad
for frames in rows:
    x = pad
    for f in frames:
        p.drawPixmap(x, y + (h - f.height()) // 2, f)   # 直向置中，對齊實際觀感
        x += w + pad
    y += h + pad
p.end()

out = os.path.join(SCRATCH, "onboard.png")
sheet.save(out)
sw.apply_theme("dark")
print("\nOK ->", out)
sys.exit(1 if fails else 0)

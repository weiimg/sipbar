# -*- coding: utf-8 -*-
"""引導的每一頁定格，深淺兩套。

各頁高度不一樣是刻意的：內容多少就多高，視窗用彈簧補間過去。
所以這支不是檢查「三頁同高」，而是檢查兩件相反的事：

1. 停下來的時候，每一頁都剛好包住自己的內容——不能有大片空白（讀起來像沒做完），
   也不能切到按鈕（那就真的壞了）。
2. 補間的中途不能把內容壓扁。頁面是自然高度、由容器裁切，所以中途只會少露出
   一截，不會有任何東西被擠小。
"""
import os
import sys

SCRATCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import onboard  # noqa: E402
import stats_window as sw  # noqa: E402

from PySide6.QtCore import Qt, QPointF  # noqa: E402
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPixmap  # noqa: E402
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

    # 「試一次」還有第二個樣子：點過之後長出音效那一段。
    #
    # 那一段預設是藏著的，所以上面那一輪只看得到點之前的版本——而點之後才是
    # 使用者真的要做決定的那一格（聽到聲音、決定要不要留著）。
    # 它比點之前高一截，最容易被切到按鈕，一定要有人用眼睛看過。
    win._go(win.page_index["try"])
    win._on_tried()
    win.sp_h.snap()
    win._apply_height()
    app.processEvents()
    tried = win.deck.pages[win.page_index["try"]]
    check(win.height() - onboard.CHROME == tried.height(),
          "「試一次」點過之後仍然剛好包住內容",
          f"視窗內容區 {win.height() - onboard.CHROME}px / 頁面 {tried.height()}px")
    actions = tried.layout().itemAt(tried.layout().count() - 1).widget()
    check(actions.geometry().bottom() <= tried.height(),
          "點過之後按鈕沒有被音效那一段擠出去",
          f"按鈕底部 {actions.geometry().bottom()} / 可視 {tried.height()}")
    frames.append(win.grab())

    # 補間中途：把高度停在一半，頁面的內部尺寸不能跟著縮。
    #
    # 要驗的是放著預覽動畫的那一頁，因為它是唯一有固定尺寸內容的頁面。
    # 頁碼用找的不是寫死的：作息頁插進來時它從 2 變成 3，而寫死的版本不會報錯，
    # 只會在另一頁上找不到預覽、拿兩個空清單去比，然後以一句看不懂的訊息紅掉。
    howto = next(i for i, pg in enumerate(win.deck.pages)
                 if pg.findChildren(type(win.preview)))
    win._go(0)
    win._h_from, win._h_to = win.deck.natural(howto), win.deck.natural(0)
    win.deck.show_page(howto)
    before = [w.size() for w in win.deck.pages[howto].findChildren(type(win.preview))]
    win.sp_h.value = 0.5
    win._apply_height()
    app.processEvents()
    after = [w.size() for w in win.deck.pages[howto].findChildren(type(win.preview))]
    check(before == after and before, "補間中途沒有壓扁內容",
          f"預覽尺寸 {before[0].width()}x{before[0].height()}" if before else "")

    print(f"  各頁高度 {[f.height() for f in frames]}")
    return frames


def check_clipping():
    """滑入時藥丸必須被螢幕上緣裁掉，不能畫到外框那一圈上面。

    整張示意圖的意思就靠這一段：它是從螢幕外面滑進來的。沒有裁切的話
    藥丸會浮在外框上，看起來像貼在圖上面的標籤，位置關係就沒說到。
    這也是為什麼不再需要「螢幕上緣」那行小字——需要旁白的示意圖等於沒說清楚。

    不比顏色。外框（22,24,28）跟藥丸（30,31,36 -> 14,15,18）幾乎同色，
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

print("")
print("最後一步：練過了才能按「開始」")
# 這一頁跟前面幾頁的「不擋」相反，是刻意的：這是整份引導裡唯一「做過」與
# 「看過」有差的一步，而這個工具最大的問題就是平常完全隱藏、找不到。
_cb = {}
_done = []
gw = onboard.open_window(lambda r: _done.append(r),
                         on_practice=lambda fn: _cb.update(fn=fn))
gw.frame.stop()
app.processEvents()
gw._go(gw.page_index["try"])
app.processEvents()
check(not gw.start_btn._enabled, "還沒練習時「開始」是灰的")
check(len(gw.skip_links) == len(gw.deck.pages), "每一頁都有「略過導覽」",
      f"連結 {len(gw.skip_links)} 個 / 頁面 {len(gw.deck.pages)} 頁")

gw.start_btn.mousePressEvent(QMouseEvent(
    QMouseEvent.MouseButtonPress, QPointF(5, 5),
    Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
app.processEvents()
check(not _done, "灰的時候點下去不會結束引導")
# 也要擋直接發訊號的路徑。檢查只寫在 mousePressEvent 的話，日後加鍵盤操作
# 或任何程式呼叫都會整個穿過去，而閘門看起來還在。
gw.start_btn.clicked.emit()
app.processEvents()
check(not _done, "直接觸發 clicked 也擋得住")

_cb["fn"]()                      # 使用者真的在島上點了一下
app.processEvents()
check(gw.start_btn._enabled, "練習完成後「開始」才亮起來")

# 擋住不能變成關不掉：這個視窗沒有 Esc 也沒有關閉鍵，練習若因故觸發不了
# （島沒出來、螢幕判定有問題），使用者只剩工作管理員一條路。
# 出口是動作列最左邊的「略過導覽」，每一頁都在、位置固定。
#
# 位置要在這裡釘死。這是桌面精靈不是手機引導：慣例是次要動作靠左、
# 主要動作靠右。放左下還有兩個實際理由——離「開始」最遠（放棄流程的動作不該
# 貼著完成流程的動作），以及右上角是角色的地盤（杯子、向上箭頭），
# 擠進去會讓箭頭看起來在指它。
_try = gw.deck.pages[gw.page_index["try"]]
_link = [w for w in _try.findChildren(sw.TapLabel) if w.text() == "略過導覽"][0]
_lx = _link.mapTo(gw, _link.rect().topLeft())
_sx = gw.start_btn.mapTo(gw, gw.start_btn.rect().topLeft())
_cue = gw.up_cue.mapTo(gw, gw.up_cue.rect().bottomRight())
check(_lx.x() < _sx.x(), "「略過導覽」在動作列最左，主要動作在最右",
      f"連結 x={_lx.x()} / 開始 x={_sx.x()}")
check(_lx.y() > _cue.y(), "在向上箭頭的下方，不會被讀成箭頭指的目標",
      f"連結 y={_lx.y()} / 箭頭底部 y={_cue.y()}")

_skipped = []
gw2 = onboard.open_window(lambda r: _skipped.append(r), on_practice=lambda fn: None)
gw2.frame.stop()
app.processEvents()
_first = [w for w in gw2.deck.pages[0].findChildren(sw.TapLabel)
          if w.text() == "略過導覽"]
check(len(_first) == 1, "第一頁就有「略過導覽」")
gw2._go(gw2.page_index["try"])
app.processEvents()
check(not gw2.start_btn._enabled, "略過導覽存在時「開始」仍然是灰的")
gw2._skip()
app.processEvents()
check(bool(_skipped), "略過導覽走得掉，不必先練習")
gw.hide()
gw2.hide()

out = os.path.join(SCRATCH, "onboard.png")
sheet.save(out)
sw.apply_theme("dark")
print("\nOK ->", out)
sys.exit(1 if fails else 0)

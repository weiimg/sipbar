# -*- coding: utf-8 -*-
"""像素風表情。水位負責「還剩多少」，表情負責「牠現在怎麼樣」。

為什麼表情不做進 Lottie 裡：
    像素風的前提是每一格都落在整數像素上。Lottie 是向量、rlottie 會抗鋸齒，
    在展開 60px 與收合 22px 兩種尺寸下縮放比例都不是整數，格子會糊掉——
    那就不是像素風，只是一張小圖。所以表情由 Qt 直接畫整數 QRect，
    跟「非整數變形會讓 Qt 關掉 hinting、字就糊了」是同一條教訓。

格子是 9x9。要改表情直接改下面的字串圖，不用動程式。
"""
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter

# 跟 island.py 用同一組字串，省掉一層狀態轉換
NORMAL, THIRSTY, WEAK, COLLAPSED, SATISFIED = "NORMAL", "THIRSTY", "WEAK", "COLLAPSED", "SATISFIED"

# 狀態 -> 水位。忽略它水就一格一格少掉，喝了就滿回來。
LEVEL = {NORMAL: 1.00, THIRSTY: 0.70, WEAK: 0.35, COLLAPSED: 0.00, SATISFIED: 1.00}

# 顏色。水永遠是水的顏色——**狀態改由水位與表情表達，不再靠色相**。
# 黃色橘色的水看起來像果汁，而且顏色編碼需要記憶對照，水位不用。
GLASS = QColor(206, 212, 224)
INK = QColor(235, 235, 245)
WATER = QColor("#4FA8E8")
WATER_DONE = QColor("#4FCF8A")      # 只有達標那一下換色

# 7x7。第一版做 9x9，臉幾乎撐滿杯子、叉叉眼糊成棋盤格——
# 格子越多不等於越清楚，反而是每一格的實際像素變少，形狀就散掉了。
GRID = 7

# '#' = 有墨，'.' = 空。
# 眼睛一律用 2x2 實心塊（單一像素在小尺寸會讀成雜點），情緒主要交給嘴巴承載。
FACES = {
    # 剛喝完：嘴角上揚
    NORMAL: [
        ".......",
        ".##.##.",
        ".##.##.",
        ".......",
        "#.....#",
        ".#####.",
        ".......",
    ],
    # 口渴：眼睛照樣睜著，但嘴抿平了
    THIRSTY: [
        ".......",
        ".##.##.",
        ".##.##.",
        ".......",
        ".......",
        ".#####.",
        ".......",
    ],
    # 虛弱：眼睛半闔成一條線，嘴角往下
    WEAK: [
        ".......",
        ".......",
        ".##.##.",
        ".......",
        ".#####.",
        "#.....#",
        ".......",
    ],
    # 倒地：空掉的眼睛（只剩外框）。
    # 原本想用叉叉眼，但斜線在一格粗細下必然變成點陣，讀起來是雜訊不是 X——
    # 這是像素風的硬限制，只能改用橫豎構成的形狀。空框反而更像「沒人在家」。
    COLLAPSED: [
        ".......",
        "###.###",
        "#.#.#.#",
        "###.###",
        ".......",
        ".#####.",
        ".......",
    ],
    # 達標：嘴巴是實心的一塊（笑開），跟正常的線條微笑分得開。
    # 不用 ^ ^ 眼，理由同上——斜線讀不出來。
    SATISFIED: [
        ".......",
        ".##.##.",
        ".##.##.",
        ".......",
        ".#####.",
        ".#####.",
        ".......",
    ],
}


# 杯子也做成像素的：向量杯子配像素表情會像兩種畫風貼在一起。
# 兩側牆＋底，上方開口。
#
# 尺寸受一個硬約束：**杯子必須塞得進「口渴停留」的藥丸高度（58.4px）**。
# 那是最常出現的狀態，也正是水位最需要被看見的時候，不能在那裡退成只有臉。
# 11x12 配格距 4px = 44x48，58.4 - 48 = 10.4px 餘裕，剛好。
# （13x15 也可以，但格距只能給到 3px，像素感弱、臉也小。）
CUP_W, CUP_H = 11, 12
CUP_WALL = [(0, r) for r in range(CUP_H - 1)] + [(CUP_W - 1, r) for r in range(CUP_H - 1)] \
    + [(c, CUP_H - 1) for c in range(CUP_W)]


# 原生格距。**固定不變，不跟著藥丸的展開程度縮放。**
#
# 第一版讓格距跟著藥丸高度走（cell = 高度 × 0.6 // 15），結果杯子在展開動畫的尾端
# 反覆變小變大。原因不是擠壓效果，是展開彈簧的阻尼 0.70 本來就會過衝再震盪收斂，
# 而展開高度 100 × 0.60 = 60、60 ÷ 15 = 4 **剛好整除**——高度掉 0.1px 格距就掉一級。
#
# 調係數只是把邊界挪到別處，下次改藥丸尺寸又會中。**像素圖只有一個原生尺寸，
# 不該跟著連續動畫縮放**——這才是根本解，也是像素風本來的規則。
FACE_CELL = 4

# 收合／探頭時只畫臉，那時藥丸只有 36px 高。用 FACE_CELL 會得到 28px 的臉，
# 上下只剩 4px、右邊離進度點只有 5px，整個擠在一起。
# 3px 格距 = 21px，剛好等於舊版幾何臉的尺寸（36 × 0.60 = 21.6）——那個比例是驗過的。
PEEK_CELL = 3

# 杯子的第二個原生尺寸，給「停留」用。
#
# FACE_CELL 的杯子是 44×48，塞進展開的 100px 藥丸佔 48% 高，比例舒服；
# 但停留態藥丸只有 58px，同一個杯子就佔到 82%，看起來像從藥丸裡爆出來——
# 這正是「杯子沒跟著藥丸縮」的症狀。
#
# 不能改成跟著高度連續縮放（見 FACE_CELL 的說明，格距一抖杯子就閃）。
# 解法是給杯子第二個**固定**的原生尺寸：3px 格距 = 33×36，在 58px 藥丸裡佔 62%，
# 跟探頭時臉佔 58% 是同一個量級。切換點選在離所有停留點都遠的高度，只會單調跨過一次。
CUP_CELL_COMPACT = 3

# 切換門檻（藥丸高度，用沒有擠壓的穩定值算）。
# 停留點是 36 / 58.4 / 68 / 100，兩個門檻都落在它們之間的空檔：
#   >= 80  用 FACE_CELL（44×48）   ← 只有全展開會到
#   >= 46  用 CUP_CELL_COMPACT     ← 口渴、虛弱的停留態
#   其餘    只畫臉                  ← 探頭與收合
CUP_FULL_MIN_H = 80
CUP_COMPACT_MIN_H = 46


def cup_cell_for(pill_h):
    """依藥丸高度挑杯子的原生尺寸。回傳 0 代表塞不下，只畫臉。"""
    if pill_h >= CUP_FULL_MIN_H:
        return FACE_CELL
    if pill_h >= CUP_COMPACT_MIN_H:
        return CUP_CELL_COMPACT
    return 0


def cell_size(box_px):
    """一格幾個裝置像素。**一定要是整數**，否則格線會落在半個像素上而糊掉。"""
    return max(1, int(box_px // GRID))


def draw(p: QPainter, cx, cy, box_px, state, color: QColor):
    """把表情畫在 (cx, cy) 為中心、邊長約 box_px 的方框裡。

    實際邊長是 cell*GRID，會小於等於 box_px——寧可小一點也不要為了填滿而用小數。
    """
    cell = cell_size(box_px)
    side = cell * GRID
    draw_at_cell(p, int(round(cx - side / 2.0)), int(round(cy - side / 2.0)),
                 cell, state, color)
    return side


def draw_at_cell(p: QPainter, x0, y0, cell, state, color: QColor):
    """左上角與格距都由呼叫端指定，讓臉可以跟杯子共用同一個格子系統。"""
    rows = FACES.get(state, FACES[NORMAL])
    x0, y0, cell = int(x0), int(y0), int(cell)

    p.save()
    # 整數座標的實心方塊不需要抗鋸齒，關掉才不會在邊緣多出半透明的一層
    p.setRenderHint(QPainter.Antialiasing, False)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch != ".":
                p.drawRect(QRect(x0 + c * cell, y0 + r * cell, cell, cell))
    p.restore()
    return cell * GRID


def cup_size(cell=FACE_CELL):
    return CUP_W * cell, CUP_H * cell


def face_size(cell=FACE_CELL):
    return GRID * cell, GRID * cell


def draw_cup(p: QPainter, cx, cy, level, state, glass: QColor,
             water: QColor, ink: QColor, cell=FACE_CELL, face=True):
    """整杯畫成像素：杯壁、水位、表情。

    level 是水位 0..1（1 = 滿）。水位直接換算成「填滿幾列格子」——
    **升級機制因此變成字面上的：你忽略它，水就一格一格少掉。**
    格數本身就是刻度，不需要另外畫進度條。
    """
    w, h = cup_size(cell)
    x0 = int(round(cx - w / 2.0))
    y0 = int(round(cy - h / 2.0))

    def put(c, r, color):
        p.setBrush(color)
        p.drawRect(QRect(x0 + c * cell, y0 + r * cell, cell, cell))

    p.save()
    p.setRenderHint(QPainter.Antialiasing, False)
    p.setPen(Qt.NoPen)

    inner_rows = CUP_H - 1                      # row 0..13 是內部，14 是杯底
    filled = int(round(max(0.0, min(1.0, level)) * inner_rows))
    for r in range(inner_rows - filled, inner_rows):
        for c in range(1, CUP_W - 1):
            put(c, r, water)
    for c, r in CUP_WALL:
        put(c, r, glass)
    p.restore()

    # 表情畫在杯子上半部：水退下去之後臉會逐漸露在空杯裡，
    # 所以墨色要選在水色與底色上都讀得到的亮色。
    # **格子大小要跟杯子共用同一個 cell**，混用兩種格距在像素風裡一眼就看得出來。
    #
    # face=False 是給小尺寸 icon 用的：格距 1–2px 時臉只有 7–14px，糊成一團反而
    # 破壞杯子的輪廓。小圖示要的是「一眼認出這是什麼」，不是細節。
    if face:
        draw_at_cell(p, x0 + (CUP_W - GRID) // 2 * cell, y0 + 3 * cell, cell, state, ink)
    return w, h

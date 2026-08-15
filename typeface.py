"""隨程式散布的字體：載入、驗證、產生 QFont。

**為什麼是內嵌字體，不是 fallback chain。**

業界三種做法，由輕到重：靠系統字體（Windows 的 font linking 自動接手中日韓）、
fallback chain（CSS 的 `font-family`，Qt 對應 `setFamilies`）、內嵌字體。
多數工具用前兩種就夠了，因為它們只需要「有字」。

這個專案需要的是「是那個字」。選 Noto Sans TC 不是因為好看，是因為它有真正的
Medium 500（exactMatch），而 Microsoft JhengHei UI 只有 Regular / Light / Bold。
內文一律用 Medium 就是在補償「淺色字放在深色底上會顯得薄」——半透明視窗吃不到
ClearType 次像素渲染，只能靠字重補。

所以退回 JhengHei UI 不是「換一個字體」，是把當初解掉的問題原封放回來，
而且是靜默的：使用者不會看到任何錯誤，只會覺得這程式的字很糊。

`FALLBACKS` 因此不是主力，是字體檔掉了之後的最後保險。真正的保證是 `ensure_loaded()`
把檔案載進來，並且**驗證真的拿到了**——`setFamily()` 要不到會靜默替換成別的字體，
這是 Qt 的老陷阱，本專案已經被同一類「靜默失敗」咬過五次（IE 開不了 HTML、
mock 掉輸入的測試、rlottie 的中文路徑、QBuffer 提早回收、offscreen 平台參數）。

授權：Noto Sans TC 是 SIL Open Font License 1.1，可以隨軟體散布（含商用與閉源），
條件是附上授權條文、不單獨販售字體。見 assets/fonts/README.md。
"""

import os

from PySide6.QtGui import QFont, QFontDatabase, QFontInfo

FAMILY = "Noto Sans TC"

# 只有兩個字重會被要求：Bold 700（display/title/section/headline）與
# Medium 500（body/caption 與島的小標）。Regular 400 全專案沒有任何地方用到，
# 所以不隨附——多 5.4MB 換一個沒人叫的字重不划算。
BUNDLED = ("NotoSansTC-Bold.otf", "NotoSansTC-Medium.otf")

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")

# **只有隨附字體載不起來時才會用到這串。** 平常路徑一個字體都不多掛——
# 理由見 make()：中文字體進了字體序列就會被整份載進記憶體，一個要價數百 MB。
FALLBACKS = (FAMILY, "Microsoft JhengHei UI", "Microsoft JhengHei", "Noto Sans CJK TC")

_state = None       # (ok: bool, detail: str)，只算一次
_cache = {}


def ensure_loaded():
    """把隨附的字體載進 Qt，回傳 (成功, 說明)。

    必須在 QApplication 建立之後呼叫——QFontDatabase 與 QFontInfo 都要有
    QGuiApplication 才能運作。重複呼叫只會做一次。
    """
    global _state
    if _state is not None:
        return _state

    loaded, missing, failed = [], [], []
    for name in BUNDLED:
        path = os.path.join(FONT_DIR, name)
        if not os.path.exists(path):
            missing.append(name)
            continue
        # Qt6 起 addApplicationFont 是靜態方法。-1 = 載入失敗（檔案壞了或格式不支援）。
        fid = QFontDatabase.addApplicationFont(path)
        if fid == -1:
            failed.append(name)
        else:
            loaded.extend(QFontDatabase.applicationFontFamilies(fid))

    # 光看 addApplicationFont 的回傳值不夠：它成功只代表「檔案讀進來了」，
    # 不代表待會 QFont(FAMILY) 就會拿到它。要實際問一次才算數。
    #
    # 而且只問 QFontInfo 也不夠——Qt 對家族名做模糊比對，連
    # QFont("Noto Sans TC No Such") 都會被解析成 "Noto Sans TC"（實測）。
    # 所以真正的判準是「這個家族有沒有在字體資料庫裡」，QFontInfo 只用來
    # 回報「實際會拿到什麼」給使用者看。
    installed = FAMILY in QFontDatabase.families()
    probe = QFont(FAMILY)
    probe.setPixelSize(17)
    actual = QFontInfo(probe).family()
    ok = installed and actual == FAMILY

    if ok:
        detail = f"使用內嵌的 {FAMILY}"
        if missing or failed:
            # 系統本來就裝了，所以還是拿得到——但發布給別人時就不會了
            detail = f"使用系統已安裝的 {FAMILY}（隨附字體未載入）"
    else:
        why = []
        if missing:
            why.append(f"缺少 {'、'.join(missing)}")
        if failed:
            why.append(f"載入失敗 {'、'.join(failed)}")
        detail = f"退回 {actual}" + ("（" + "；".join(why) + "）" if why else "")

    _state = (ok, detail)
    return _state


def make(px, weight, tracking=0.0, family=None):
    """產生一個字體。同樣的參數只會建一次。

    用 setFamilies 而不是 setFamily：Qt 從 5.13 起才有真正的字體序列，
    逐字元往下找（跟 CSS 的 font-family 同樣語意）。
    setFamily("A, B") 這種寫法 Qt 不解析逗號，會被當成一個叫「A, B」的字體。

    `family` 只給 tests/font_ab.py 那種要換字體做 A/B 比對的場合用；
    正常路徑一律留 None，走隨附字體。
    """
    key = (px, int(weight), tracking, family)
    f = _cache.get(key)
    if f is None:
        # 自己確保字體載好，不依賴呼叫端記得先叫 ensure_loaded()。
        # 任何會呼叫到這裡的路徑都已經有 QGuiApplication（QFont 本身就需要），
        # 所以這裡叫是安全的，而且省掉一個「忘了初始化就靜默降級」的陷阱。
        ok, _ = ensure_loaded()

        # **字體序列裡每多一個中文字體，就多幾百 MB。**
        # 實測（tests/test_font_memory.py）：序列只有 Noto Sans TC 時，島畫出文字後
        # 佔 89MB；加上 Microsoft JhengHei UI 變成 612MB、handle 從 342 漲到 1153。
        # Qt 為了決定每個字元由誰來畫，會把序列上每個字體的字符表都載進來，
        # 而中文字體動輒三萬個字符。
        #
        # 所以隨附字體載成功時就**只用它一個**，不掛保險——保險在這裡不是免費的，
        # 而且 Qt 本來就有自己的系統級字元回退，缺字不會變成豆腐。
        # 只有隨附字體真的載不起來，才值得付這個代價去指定偏好的替補。
        families = [FAMILY] if ok else list(FALLBACKS)
        if family and family != FAMILY:
            families = [family] + families          # tests/font_ab.py 的 A/B 比對用
        f = QFont()
        f.setFamilies(families)
        f.setPixelSize(px)                  # 用像素不用點數：點數會經 DPI 換算成小數
        f.setWeight(weight)
        f.setStyleHint(QFont.SansSerif)     # 連 fallback 都沒中時的最後一層
        f.setHintingPreference(QFont.PreferFullHinting)
        f.setStyleStrategy(QFont.PreferAntialias)
        if tracking:
            f.setLetterSpacing(QFont.AbsoluteSpacing, tracking)
        _cache[key] = f
    return f

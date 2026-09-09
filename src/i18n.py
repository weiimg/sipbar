# -*- coding: utf-8 -*-
"""Sipbar i18n — lightweight translation layer.

Two languages: ``zh-TW`` (default) and ``en``.  The ``t(key)`` function
returns a scalar string; ``tl(key)`` returns a list.  Both look up the
current language lazily from *settings.load_config()["language"]*.
"""

import ctypes
import settings

_lang = None


def _detect_system():
    """Return ``"zh-TW"`` when the Windows UI language is Chinese."""
    try:
        ui = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "zh-TW" if (ui & 0xFF) == 0x04 else "en"
    except Exception:                                      # noqa: BLE001
        return "zh-TW"


def current():
    """Resolve and cache the effective language."""
    global _lang
    if _lang is None:
        cfg = settings.load_config()
        choice = cfg.get("language", "auto")
        if choice == "auto":
            _lang = _detect_system()
        elif choice in ("zh-TW", "en"):
            _lang = choice
        else:
            _lang = "zh-TW"
    return _lang


def set_language(lang):
    """Switch language at runtime (called by the settings page)."""
    global _lang
    _lang = lang if lang in ("zh-TW", "en") else "zh-TW"


def t(key, **kw):
    """Look up a translated string.  Falls back to zh-TW, then the key."""
    lang = current()
    table = _EN if lang == "en" else _ZH
    text = table.get(key)
    if text is None:
        text = _ZH.get(key, key)
    return text.format(**kw) if kw else text


def tl(key):
    """Look up a translated list.  Falls back to zh-TW, then ``[key]``."""
    lang = current()
    table = _EN if lang == "en" else _ZH
    result = table.get(key)
    if result is None:
        result = _ZH.get(key, [key])
    return result


# ================================================================ zh-TW
#
# 這是繁體中文的翻譯字典。介面文案受 tests/test_copy_style.py 檢查。
# 角色台詞用 copy-style: off / on 標出來。

_ZH = {

    # -------------------------------------------------------------- 角色台詞
    # copy-style: off

    # 島的訊息——口語、第二人稱都是刻意的。
    "msg.thirsty": ["口渴了", "該喝水了", "水呢", "喉嚨乾乾的", "來一口",
                     "水壺還有水嗎", "現在喝正好", "提醒一下：水", "喝一口再繼續"],
    "msg.weak": ["真的渴了", "有點虛", "撐不太住", "還是沒喝喔", "再不喝要倒了",
                 "拜託", "水……", "已經等你一陣子了", "還在等"],
    "msg.collapsed": ["倒了", "沒力了", "陣亡", "叫不動了", "放棄了",
                      "你贏了", "需要急救（一杯水）", "躺平中"],
    "msg.normal": ["水分充足", "還沒到時間", "下次再叫你"],
    "msg.done": ["今天已達標", "今天不吵你了", "收工了"],
    "msg.counted.thirsty": ["還剩 {n} 次", "喝一口，剩 {n} 次", "今天還有 {n} 次",
                            "第 {k} 次，時間到", "剩 {n} 次達標"],
    "msg.counted.weak": ["還差 {n} 次", "剩 {n} 次，先喝一口", "等你第 {k} 次",
                         "再 {n} 次就好，拜託"],
    "msg.counted.collapsed": ["倒了，還剩 {n} 次", "剩 {n} 次…救我", "第 {k} 次，救命"],
    "msg.last_call": ["最後一次了", "剩最後一次", "最後一口"],
    "msg.first_call": ["今天還沒開張", "今天第一次", "從第一次開始"],

    # 打招呼 & 練習模式
    "msg.greet": "嗨！",
    "msg.greet_sub": "游標移至螢幕上緣中央可呼叫",
    "msg.fill_water": "先去裝杯水吧",
    "msg.practice": "點我一下",
    "msg.practice_sub": "這次不會算進今天的次數",
    "msg.practice_done": "就是這樣",
    "msg.practice_done_sub": "時間到我會自己出現",
    "msg.drink_target": "今天達標了",
    "msg.drink_remaining": "喝了，還剩 {n} 次",
    "msg.hint_records": "右鍵可以看紀錄",

    # 成就名稱
    "achievement.name.1": "水啦！",
    "achievement.name.2": "今天很水哦",
    "achievement.name.3": "One, two, 水！",
    "achievement.name.4": "需要你",
    "achievement.name.5": "我是一隻魚",
    "achievement.name.6": "一氧化二氫成癮者",
    "achievement.name.7": "游過太平洋了吧",
    "achievement.name.8": "水做的",
    "achievement.name.9": "一整年",
    "achievement.name.10": "千杯之友",
    "achievement.name.11": "夜貓子",
    "achievement.name.12": "晨型人",

    # 引導——杯子的聲音
    "onboard.name": "杯子",
    "onboard.water_lead": "你只要先做一件事：把水放在手邊。"
                          "要走去廚房的話我幫不上忙，但水在旁邊，時間就交給我！",
    "onboard.fill_lead": "先去裝，我在這等你！",
    "onboard.fill_lead_song": "先去裝，我在這等你，順便配了首歌！",
    "onboard.how_1": "平常我不會出現，時間到才從螢幕上緣滑下來",
    "onboard.how_2": "點我一下就算喝了，右鍵可以看紀錄",
    "onboard.how_3": "沒有關閉按鈕，喝完我就自己回去了",
    "onboard.how_settings": "覺得太吵或不夠，設定裡都可以改。"
                            "右鍵選單或紀錄視窗右上角的齒輪都進得去。",
    "onboard.try_lead": "我跑到螢幕最上面了，看得到嗎？",
    "onboard.try_done": "就是這樣。之後時間到我就會這樣出現。",
    "onboard.try_sound": "剛剛那一聲，是我等太久的時候會發出的。"
                         "平常都是安靜的，不想要現在就可以關掉。",

    # copy-style: on
    # -------------------------------------------------------------- 介面文案

    # 成就說明
    "achievement.desc.1": "完成一次補水",
    "achievement.desc.2": "一天內補水 {t} 次",
    "achievement.desc.3": "連續三天達標",
    "achievement.desc.4": "連續七天達標",
    "achievement.desc.5": "總補水次數達 100",
    "achievement.desc.6": "連續三十天達標",
    "achievement.desc.7": "總補水次數達 500",
    "achievement.desc.8": "累積達標 100 天",
    "achievement.desc.9": "累積達標 365 天",
    "achievement.desc.10": "總補水次數達 1000",
    "achievement.desc.11": "深夜補水 10 次",
    "achievement.desc.12": "清晨補水 10 次",
    "achievement.done": "完成",

    # 星期
    "weekdays": "一二三四五六日",

    # 健康提示
    "tips": [
        "身體約有六成是水",
        "血漿約九成是水",
        "腦脊髓液幾乎都是水",
        "骨頭裡也含有水分",
        "肌肉的含水量高於脂肪",
        "腎臟一天過濾約 180 公升",
        "消化液一天分泌約 7 公升",
        "唾液一天約分泌 1 公升",
        "口渴由下視丘偵測",
        "血液變濃時會感到口渴",
        "流汗靠蒸發帶走熱",
        "呼吸也會帶走水分",
        "關節靠滑液減少摩擦",
        "身體無法預先儲存水分",
        "輕微缺水會影響注意力",
        "缺水 2% 會影響運動表現",
        "流汗帶走的不只是水",
        "水分夠時尿液顏色偏淡",
        "一小時內不超過 1000cc",
        "小口分次比一次喝完好",
        "起床後建議 300-500cc",
        "體重每公斤約需 30cc",
        "一杯水約 240cc",
        "白開水是最直接的選擇",
        "冰涼的水通常喝得比較多",
        "水杯放在看得見的地方",
        "固定時間喝比靠記憶可靠",
        "餐前一杯水是好記的時機",
        "咖啡和茶也算水分來源",
        "約兩成水分來自食物",
        "湯和水果也提供水分",
        "需要的水量因人而異",
        "水分建議量男女不同",
        "冷氣房空氣乾，蒸散更快",
        "天冷時口渴的感覺變弱",
        "睡覺時身體持續流失水分",
        "流汗多的日子需要多補",
        "講話多時聲帶需要水分",
    ],

    # --- 島的狀態行 ---
    "status.write_trouble": "紀錄存不進去",
    "status.paused": "暫停中，{time} 恢復",
    "status.streak": "連續 {n} 天",
    "status.grace_warning": "{n} 天連勝即將消失，今天達標可挽回",
    "status.grace_recovered": "連續 {n} 天保住了！",
    "status.today_count": "今天 {done}/{target} 次",
    "status.target_reached": "今天已達標",
    "status.coming_soon": "快到了",
    "status.next_in": "下次約 {n} 分後",
    "remind.today_count": "今天補水 {done}/{target} 次",

    # --- 對話方塊 ---
    "dialog.already_running": "{app} 已經在執行中。動態島的入口在螢幕頂端中央。"
                              "\n\n若沒有任何反應，請在工作管理員結束 {app} 再重新開啟。",
    "dialog.records_error_title": "開不了紀錄",
    "dialog.records_error_body": "開啟紀錄視窗時出錯：\n{err}",

    # --- 系統匣 ---
    "tray.started_title": "{app} 已啟動",
    "tray.started_body": "系統匣圖示顯示為 pythonw，可拖曳至工作列固定。"
                         "\n將游標移至螢幕上緣中央亦可隨時顯示。",

    # --- 右鍵選單 ---
    "menu.head": "今天 {done} / {target} 次",
    "menu.paused": "已暫停，{time} 恢復",
    "menu.done": "約 {cc} cc，今日已達標",
    "menu.soon": "即將提醒",
    "menu.next_in": "下次約 {n} 分後",
    "menu.active": "約 {cc} cc，{when}",
    "menu.drink": "記錄補水",
    "menu.undo": "退回上一次記錄",
    "menu.resume": "恢復提醒",
    "menu.pause": "暫停提醒 2 小時",
    "menu.records": "喝水紀錄",
    "menu.settings": "設定",
    "menu.quit": "結束程式",

    # --- 引導按鈕 & 頁面 ---
    "onboard.skip": "略過導覽",
    "onboard.back": "上一步",
    "onboard.yes": "有，繼續",
    "onboard.not_yet": "還沒有",
    "onboard.filled": "裝好了",
    "onboard.next": "下一步",
    "onboard.start": "開始",
    "onboard.page_water": "開始之前",
    "onboard.page_fill": "先去裝一壺",
    "onboard.page_schedule": "作息",
    "onboard.schedule_q": "習慣幾點就寢？",
    "onboard.schedule_note": "就寢前三小時起自動放慢提醒。",
    "onboard.bedtime_label": "就寢",
    "onboard.page_howto": "這樣用",
    "onboard.autostart": "開機時啟動",
    "onboard.page_try": "試一次",
    "onboard.sound_label": "提醒音效",
    "onboard.water_q": "桌上現在有水嗎？",

    # --- 頁籤 ---
    "tab.today": "今天",
    "tab.history": "紀錄",
    "tab.achievements": "成就",
    "tab.start": "開始",

    # --- 連續卡片 ---
    "streak.reached": "達標！連續第 {n} 天",
    "streak.reached_today": "今天達標！",
    "streak.more_streak": "再 {left} 次，連續來到第 {n} 天",
    "streak.more": "還差 {n} 次達標",
    "streak.not_started": "今天還沒開始",
    "streak.cup_tip": "今天 {done} / {target} 次",
    "streak.unit_days": "天",
    "streak.consecutive": "連續達標",
    "streak.shields": "護盾",
    "grace.stats_countdown": "{n} 天連勝即將消失（剩 {h} 時 {m} 分），再 {left} 次可挽回",
    "grace.stats_recovering": "達標！{n} 天連勝保住了",
    "grace.notify_title": "連勝即將消失",
    "grace.notify_body": "你的 {n} 天連勝快斷了，今天達標就能挽回",
    "grace.recovered_title": "連勝保住了！",
    "grace.recovered_body": "連續 {n} 天的紀錄安全了",
    "grace.expired_title": "你不要我了嗎？",
    "grace.expired_body": "喝點水再繼續吧",

    # --- 杯子計量 ---
    "cup.count": "{done} / {target} 次",
    "cup.cc": "約 {done} / {target} cc",

    # --- 週曆提示 ---
    "week.future": "還沒到",
    "week.hit": "{n} / {target} 次，達標",
    "week.partial": "{n} / {target} 次",
    "week.inactive": "沒開電腦，不計入連續",

    # --- 熱圖提示 ---
    "heatmap.shield_used": "{n} / {target} 次，護盾已消耗",
    "heatmap.count": "{n} / {target} 次",
    "heatmap.inactive": "沒開電腦，不計入連續",

    # --- 紀錄卡片 ---
    "card.week": "本週",
    "card.trail": "紀錄",
    "stat.longest": "最長連續（天）",
    "stat.total": "累積補水（次）",
    "stat.liters": "估算水量（公升）",
    "card.achievements": "成就",
    "stat.response_rate": "提醒回應率",
    "stat.avg_time": "平均回應時間",
    "unit.min_short": "分",

    # --- 護盾提示 ---
    "shield.tip_full": "保持水分！",
    "shield.tip_partial": "還剩 {n} 個，再達標 {d} 天多一個",

    # --- 空狀態 ---
    "empty.title": "還沒有紀錄",
    "empty.instruction": "點擊動態島即可記錄補水",
    "empty.hint": "首次記錄後開始累積",

    # --- 設定頁 ---
    "settings.reminder": "提醒",
    "settings.weight": "體重",
    "unit.kg": "公斤",
    "settings.interval": "提醒間隔",
    "unit.minutes": "分鐘",
    "settings.interval_hint": "以鍵盤滑鼠的活動時間計算",
    "settings.bedtime": "預計就寢時間",
    "settings.bedtime_auto": "改為自動",
    "settings.sound": "提醒音效",
    "settings.sound_hint": "僅於提醒被忽略時發出",
    "settings.sound_after": "忽略 {n} 分鐘後",
    "settings.display": "顯示",
    "theme.auto": "跟隨系統",
    "theme.light": "淺色",
    "theme.dark": "深色",
    "settings.appearance": "外觀",
    "settings.screen_n": "螢幕 {n}",
    "settings.screen": "動態島顯示在",
    "settings.autostart": "開機時啟動",
    "settings.updates": "檢查更新",
    "settings.updates_hint": "啟動時向 GitHub 查詢新版本",
    "settings.about": "關於",
    "settings.language": "語言",
    "lang.auto": "自動",
    "lang.zh": "繁體中文",
    "lang.en": "English",
    "action.open": "開啟",
    "about.data": "資料位置",
    "about.version_update": "有新版 {tag}",
    "about.version": "版本",
    "about.report": "回報問題",
    "action.copy": "複製",
    "about.diagnostics": "診斷資訊",
    "about.diagnostics_value": "系統與版本資訊",
    "action.view_again": "再看一次",
    "about.guide": "使用導覽",
    "about.privacy": "本程式不蒐集也不傳送任何資料，全部僅儲存於本機。",
    "about.disclaimer": "每日目標依國民健康署的公開資料與體重推算，"
                        "不構成醫療建議。僅涵蓋使用電腦期間，"
                        "未計入運動或流汗的額外需求。",

    # --- 音效設定 ---
    "sound.preview": "試聽",
    "sound.choose": "選擇",
    "sound.restore": "還原",
    "sound.invalid": "不是 WAV 格式，仍使用內建",
    "sound.custom": "自訂",
    "sound.builtin": "內建",
    "sound.picker_title": "選擇提醒音效",
    "sound.picker_filter": "音效檔 (*.wav)",
    "sound.pick_error": "選的檔案不是 WAV 格式",
    "placeholder.optional": "選填",

    # --- 作息 & 目標標籤 ---
    "schedule.manual": "手動指定",
    "schedule.inferred": "依活動紀錄推算",
    "schedule.estimated": "推估值，累積足夠紀錄後自動校準",
    "target.from_weight": "由體重推算",
    "target.default": "預設值",
    "target.label": "{src}：每日目標 {t} 次，約 {ml} cc",
    "late.interval": "睡前 {h} 小時起改為每 {mins} 分",
    "late.manual": "手動指定，{tail}",
    "late.estimated": "推估值，累積足夠紀錄後自動校準，{tail}",
    "late.inferred": "依活動紀錄推算，{tail}",

    # --- 清除紀錄 ---
    "danger.action": "清除紀錄",
    "danger.note": "移除所有補水紀錄與連續天數，設定保留",
    "confirm.delete": "刪除",
    "confirm.cancel": "取消",
    "confirm.reset_title": "清除所有紀錄？",
    "confirm.reset_body": "移除所有補水紀錄與連續天數，設定保留。此動作無法復原。",

    # --- 視窗標題 & 導覽 ---
    "window.title": "喝水紀錄",
    "title.stats": "喝水紀錄",
    "title.settings": "設定",
    "breadcrumb.back": "‹ 喝水紀錄",
    "subtitle.goal": "每日目標 {target} 次",
    "action.copied": "已複製",

    # --- 診斷資訊 ---
    "diag.theme.auto": "跟隨系統",
    "diag.theme.light": "淺色",
    "diag.theme.dark": "深色",
    "diag.face.pixel": "像素",
    "diag.face.geometry": "幾何",
    "diag.screens": "螢幕 {n} 個，主要 {w}x{h}，縮放 {pct}%",
    "diag.font.embedded": "內嵌",
    "diag.font.fallback": "系統替代",
    "diag.font": "字體 {value}",
    "diag.appearance": "外觀 {theme}，角色 {face}",
    "diag.target": "每日目標 {t} 次",
    "diag.target.weight": "依體重推導",
    "diag.target.default": "預設",
    "diag.interval": "提醒間隔 {n} 分鐘",
    "diag.crash": "崩潰紀錄 {summary}",
    "diag.update": "檢查更新 {status}",
    "diag.write_fail": "寫入失敗 連續 {n} 次",
    "diag.repaired": "設定值退回預設",
    "diag.file_missing": "不存在",
    "diag.file_error": "讀取失敗 {error}",
    "diag.file": "資料檔 {path} -> {stat}",
    "diag.file_actual": "視窗實際讀 {path} -> {stat}",

    # --- crashlog / updates / typeface 狀態 ---
    "crash.none": "無",
    "crash.has_records": "有紀錄（{size} bytes）",
    "crash.count": "{n} 筆",
    "crash.read_fail": "讀取失敗",
    "crash.trimmed": "（較舊的紀錄已因檔案大小上限被清除）",
    "updates.disabled": "未啟用",
    "updates.checking": "查詢中",
    "updates.ok": "成功",
    "updates.fail": "失敗",
    "typeface.using": "使用內嵌的 {family}",
    "typeface.system": "使用系統已安裝的 {family}（隨附字體未載入）",
    "typeface.missing": "缺少 {names}",
    "typeface.load_fail": "載入失敗 {names}",
    "typeface.fallback": "退回 {actual}",

    # --- 音效說明檔（寫到磁碟的說明文件，不是介面文案） ---
    # copy-style: off
    "sound.readme_name": "說明.txt",
    "sound.readme_text": (
        "自訂提醒音效\n\n"
        "平常不必用到這個資料夾——設定頁的「提醒音效」底下有「選擇」，挑完會自動\n"
        "複製進來。這份說明是給想直接放檔案的人看的。\n\n"
        "把音檔放進這個資料夾，檔名必須是下面兩個之一：\n\n"
        "    weak.wav        被忽略 15 分鐘時播（內建版是往上的兩聲）\n"
        "    collapsed.wav   被忽略 40 分鐘時播（內建版是往下的兩聲）\n\n"
        "只放一個也可以，另一個會繼續用內建的。\n"
        "刪掉檔案就回到內建，不需要改任何設定。\n\n"
        "格式：WAV。mp3 或 m4a 改名成 .wav 不會生效，設定頁會顯示「不是 WAV 格式」。\n\n"
        "音量由檔案本身決定，程式不會幫你調整——Windows 用系統音量播放，\n"
        "程式在播的時候沒有辦法調小。內建那兩個的尖峰壓在滿刻度的 26%，\n"
        "自己做的話可以拿它當基準。\n\n"
        "內建的音檔在程式資料夾的 _internal\\assets\\sound\\ 底下，\n"
        "可以複製出來當範本。\n\n"
        "設定頁那兩列各有一顆「試聽」，換完可以立刻聽。\n"
    ),
    # copy-style: on
}


# ================================================================ English

_EN = {

    # -------------------------------------------------------------- Character voice
    # copy-style: off

    "msg.thirsty": ["Thirsty", "Time for water", "Water?", "A bit dry",
                     "Take a sip", "Got your bottle?", "Good time to drink",
                     "Reminder: water", "One sip, then back to it"],
    "msg.weak": ["Really thirsty now", "Feeling weak", "Can't hold on",
                 "Still no water?", "About to collapse", "Please",
                 "Water…", "Been waiting a while", "Still waiting"],
    "msg.collapsed": ["Collapsed", "Out of energy", "Down", "Not responding",
                      "Gave up", "You win", "Need rescue (one glass)",
                      "Lying flat"],
    "msg.normal": ["Hydrated", "Not time yet", "I'll call you later"],
    "msg.done": ["Goal reached today", "Done bugging you", "Clocking out"],
    "msg.counted.thirsty": ["{n} left", "One sip, {n} to go",
                            "{n} more today", "#{k}, time's up",
                            "{n} to reach goal"],
    "msg.counted.weak": ["{n} more to go", "{n} left, take a sip",
                         "Waiting for #{k}", "Just {n} more, please"],
    "msg.counted.collapsed": ["Down, {n} left", "{n} left…save me",
                              "#{k}, help"],
    "msg.last_call": ["Last one", "One more to go", "Final sip"],
    "msg.first_call": ["Haven't started today", "First one today",
                       "Starting from #1"],

    "msg.greet": "Hi!",
    "msg.greet_sub": "Move cursor to top center to summon",
    "msg.fill_water": "Go fill your water bottle",
    "msg.practice": "Tap me",
    "msg.practice_sub": "This one won't count",
    "msg.practice_done": "That's it",
    "msg.practice_done_sub": "I'll show up when it's time",
    "msg.drink_target": "Goal reached!",
    "msg.drink_remaining": "Done, {n} left",
    "msg.hint_records": "Right-click for records",

    "achievement.name.1": "Hydrated!",
    "achievement.name.2": "So hydrated today",
    "achievement.name.3": "One, two, water!",
    "achievement.name.4": "Need you",
    "achievement.name.5": "I'm a fish",
    "achievement.name.6": "H₂O addict",
    "achievement.name.7": "Swam the Pacific",
    "achievement.name.8": "Made of water",
    "achievement.name.9": "Full year",
    "achievement.name.10": "1000 club",
    "achievement.name.11": "Night owl",
    "achievement.name.12": "Early bird",

    "onboard.name": "Cup",
    "onboard.water_lead": ("First things first: keep water within reach. "
                           "I can't help with the trip to the kitchen, "
                           "but once it's beside you, leave the timing to me!"),
    "onboard.fill_lead": "Go fill up — I'll wait right here!",
    "onboard.fill_lead_song": "Go fill up — I'll wait right here, "
                              "with a little tune!",
    "onboard.how_1": "I stay hidden; I only slide down when it's time",
    "onboard.how_2": "Tap me once to log a drink; right-click for records",
    "onboard.how_3": "No close button — I go away on my own after you drink",
    "onboard.how_settings": ("Too much or too little? "
                             "You can change everything in Settings. "
                             "Right-click menu or the gear icon in the log."),
    "onboard.try_lead": "I'm at the very top of the screen — see me?",
    "onboard.try_done": "That's it. I'll show up like this when it's time.",
    "onboard.try_sound": ("That little sound plays when I've been waiting "
                          "too long. I'm usually silent — turn it off "
                          "right now if you prefer."),

    # copy-style: on
    # -------------------------------------------------------------- UI copy

    "achievement.desc.1": "Complete one hydration",
    "achievement.desc.2": "Hydrate {t} times in a day",
    "achievement.desc.3": "Reach the goal 3 days in a row",
    "achievement.desc.4": "Reach the goal 7 days in a row",
    "achievement.desc.5": "Reach 100 total hydrations",
    "achievement.desc.6": "Reach the goal 30 days in a row",
    "achievement.desc.7": "Reach 500 total hydrations",
    "achievement.desc.8": "Hit your daily goal 100 days",
    "achievement.desc.9": "Hit your daily goal 365 days",
    "achievement.desc.10": "Reach 1000 total hydrations",
    "achievement.desc.11": "Hydrate 10 times in the wee hours",
    "achievement.desc.12": "Hydrate 10 times in the early morning",
    "achievement.done": "Done",

    "weekdays": "MTWTFSS",

    "tips": [
        "~60% of your body is water",
        "Blood plasma is ~90% water",
        "Spinal fluid is nearly all water",
        "Even bones contain water",
        "Muscles hold more water than fat",
        "Kidneys filter ~180 L per day",
        "Digestive juices: ~7 L/day",
        "You produce ~1 L saliva daily",
        "Thirst is sensed by the brain",
        "Thicker blood triggers thirst",
        "Sweat cools you by evaporating",
        "You lose water just breathing",
        "Joints rely on fluid to move",
        "Your body can't store water",
        "Mild dehydration hurts focus",
        "2% loss impairs performance",
        "Sweat carries more than water",
        "Pale urine = good hydration",
        "Max ~1000 cc per hour",
        "Small sips beat chugging",
        "300-500 cc after waking up",
        "~30 cc per kg of body weight",
        "One glass is about 240 cc",
        "Plain water is the best choice",
        "Cold water: you drink more",
        "Keep a glass where you can see",
        "A schedule beats willpower",
        "Before meals is easy to recall",
        "Coffee and tea count too",
        "~20% of water comes from food",
        "Soups and fruit provide water",
        "Water needs vary per person",
        "Men and women differ in needs",
        "AC dries the air; drink more",
        "Cold weather dulls thirst",
        "You lose water while sleeping",
        "Sweaty days need extra water",
        "Talking a lot dries the throat",
    ],

    # --- Island status ---
    "status.write_trouble": "Records can't be saved",
    "status.paused": "Paused, resuming at {time}",
    "status.streak": "{n}-day streak",
    "status.grace_warning": "{n}-day streak at risk — reach goal today to save it",
    "status.grace_recovered": "{n}-day streak saved!",
    "status.today_count": "Today {done}/{target}",
    "status.target_reached": "Target reached today",
    "status.coming_soon": "Coming soon",
    "status.next_in": "Next in ~{n} min",
    "remind.today_count": "Today {done}/{target}",

    # --- Dialogs ---
    "dialog.already_running": ("{app} is already running. "
                               "The island is at the top center of your screen."
                               "\n\nIf nothing responds, end {app} in "
                               "Task Manager and reopen it."),
    "dialog.records_error_title": "Cannot open records",
    "dialog.records_error_body": "Error opening records window:\n{err}",

    # --- Tray ---
    "tray.started_title": "{app} started",
    "tray.started_body": ("The tray icon shows as pythonw — "
                          "drag it to the taskbar to pin."
                          "\nMove cursor to top center to show anytime."),

    # --- Context menu ---
    "menu.head": "Today {done} / {target}",
    "menu.paused": "Paused, resuming at {time}",
    "menu.done": "~{cc} cc, target reached",
    "menu.soon": "Reminder soon",
    "menu.next_in": "Next in ~{n} min",
    "menu.active": "~{cc} cc, {when}",
    "menu.drink": "Log water",
    "menu.undo": "Undo last entry",
    "menu.resume": "Resume reminders",
    "menu.pause": "Pause for 2 hours",
    "menu.records": "Water log",
    "menu.settings": "Settings",
    "menu.quit": "Quit",

    # --- Onboarding buttons & pages ---
    "onboard.skip": "Skip tour",
    "onboard.back": "Back",
    "onboard.yes": "Yes, continue",
    "onboard.not_yet": "Not yet",
    "onboard.filled": "All set",
    "onboard.next": "Next",
    "onboard.start": "Start",
    "onboard.page_water": "Before you start",
    "onboard.page_fill": "Go fill up first",
    "onboard.page_schedule": "Schedule",
    "onboard.schedule_q": "What time do you usually go to bed?",
    "onboard.schedule_note": "Reminders slow down 3 hours before bedtime.",
    "onboard.bedtime_label": "Bedtime",
    "onboard.page_howto": "How to use",
    "onboard.autostart": "Start on boot",
    "onboard.page_try": "Try it once",
    "onboard.sound_label": "Reminder sound",
    "onboard.water_q": "Do you have water on your desk?",

    # --- Tabs ---
    "tab.today": "Today",
    "tab.history": "History",
    "tab.achievements": "Achievements",
    "tab.start": "Start",

    # --- Streak card ---
    "streak.reached": "Goal! Day {n} in a row",
    "streak.reached_today": "Goal reached today!",
    "streak.more_streak": "{left} more for day {n}",
    "streak.more": "{n} more to reach goal",
    "streak.not_started": "Haven't started today",
    "streak.cup_tip": "Today {done} / {target}",
    "streak.unit_days": "days",
    "streak.consecutive": "Consecutive",
    "streak.shields": "Shields",
    "grace.stats_countdown": "{n}-day streak at risk ({h}h {m}m left), {left} more to save",
    "grace.stats_recovering": "Goal! {n}-day streak saved",
    "grace.notify_title": "Streak at risk",
    "grace.notify_body": "Your {n}-day streak is about to break — reach your goal today to save it",
    "grace.recovered_title": "Streak saved!",
    "grace.recovered_body": "Your {n}-day streak is safe",
    "grace.expired_title": "Don’t leave me…",
    "grace.expired_body": "Have some water and let’s start again",

    # --- Cup gauge ---
    "cup.count": "{done} / {target}",
    "cup.cc": "~{done} / {target} cc",

    # --- Week strip tooltips ---
    "week.future": "Not yet",
    "week.hit": "{n} / {target}, reached",
    "week.partial": "{n} / {target}",
    "week.inactive": "No activity, not counted",

    # --- Heatmap tooltips ---
    "heatmap.shield_used": "{n} / {target}, shield used",
    "heatmap.count": "{n} / {target}",
    "heatmap.inactive": "No activity, not counted",

    # --- Trail card ---
    "card.week": "This Week",
    "card.trail": "History",
    "stat.longest": "Longest streak (days)",
    "stat.total": "Total hydrations",
    "stat.liters": "Est. water (liters)",
    "card.achievements": "Achievements",
    "stat.response_rate": "Reminder response rate",
    "stat.avg_time": "Avg. response time",
    "unit.min_short": "min",

    # --- Shield tooltip ---
    "shield.tip_full": "Stay hydrated!",
    "shield.tip_partial": "{n} left; {d} more days for another",

    # --- Empty state ---
    "empty.title": "No records yet",
    "empty.instruction": "Tap the island to log water",
    "empty.hint": "Tracking starts after the first entry",

    # --- Settings ---
    "settings.reminder": "Reminders",
    "settings.weight": "Weight",
    "unit.kg": "kg",
    "settings.interval": "Reminder interval",
    "unit.minutes": "min",
    "settings.interval_hint": "Based on keyboard/mouse activity",
    "settings.bedtime": "Expected bedtime",
    "settings.bedtime_auto": "Switch to auto",
    "settings.sound": "Reminder sound",
    "settings.sound_hint": "Only when a reminder is ignored",
    "settings.sound_after": "After ignoring for {n} min",
    "settings.display": "Display",
    "theme.auto": "Auto",
    "theme.light": "Light",
    "theme.dark": "Dark",
    "settings.appearance": "Appearance",
    "settings.screen_n": "Screen {n}",
    "settings.screen": "Show island on",
    "settings.autostart": "Start on boot",
    "settings.updates": "Check for updates",
    "settings.updates_hint": "Check GitHub for new versions on startup",
    "settings.about": "About",
    "settings.language": "Language",
    "lang.auto": "Auto",
    "lang.zh": "繁體中文",
    "lang.en": "English",
    "action.open": "Open",
    "about.data": "Data location",
    "about.version_update": "New version {tag}",
    "about.version": "Version",
    "about.report": "Report issue",
    "action.copy": "Copy",
    "about.diagnostics": "Diagnostics",
    "about.diagnostics_value": "System and version info",
    "action.view_again": "View again",
    "about.guide": "User guide",
    "about.privacy": "This app does not collect or transmit any data. "
                     "Everything is stored locally.",
    "about.disclaimer": ("Daily goals are estimated from public health data "
                         "and body weight; this is not medical advice. "
                         "Only covers computer time; exercise and sweating "
                         "require extra water."),

    # --- Sound settings ---
    "sound.preview": "Preview",
    "sound.choose": "Choose",
    "sound.restore": "Restore",
    "sound.invalid": "Not WAV, using built-in",
    "sound.custom": "Custom",
    "sound.builtin": "Built-in",
    "sound.picker_title": "Choose reminder sound",
    "sound.picker_filter": "Sound files (*.wav)",
    "sound.pick_error": "Selected file is not WAV format",
    "placeholder.optional": "Optional",

    # --- Schedule & target labels ---
    "schedule.manual": "Manually set",
    "schedule.inferred": "From activity log",
    "schedule.estimated": "Estimated; auto-calibrates later",
    "target.from_weight": "From weight",
    "target.default": "Default",
    "target.label": "{src}: daily goal {t}, ~{ml} cc",
    "late.interval": "Every {mins} min from {h}h before bed",
    "late.manual": "Manual, {tail}",
    "late.estimated": "Estimated, auto-calibrates, {tail}",
    "late.inferred": "From activity log, {tail}",

    # --- Danger zone ---
    "danger.action": "Clear records",
    "danger.note": "Remove all hydration records and streaks; settings kept",
    "confirm.delete": "Delete",
    "confirm.cancel": "Cancel",
    "confirm.reset_title": "Clear all records?",
    "confirm.reset_body": "Remove all hydration records and streaks. "
                          "Settings are preserved. This cannot be undone.",

    # --- Window titles & navigation ---
    "window.title": "Water Log",
    "title.stats": "Water Log",
    "title.settings": "Settings",
    "breadcrumb.back": "‹ Water Log",
    "subtitle.goal": "Daily goal: {target}",
    "action.copied": "Copied",

    # --- Diagnostics ---
    "diag.theme.auto": "Auto",
    "diag.theme.light": "Light",
    "diag.theme.dark": "Dark",
    "diag.face.pixel": "Pixel",
    "diag.face.geometry": "Geometry",
    "diag.screens": "{n} screens, primary {w}x{h}, scale {pct}%",
    "diag.font.embedded": "Embedded",
    "diag.font.fallback": "System fallback",
    "diag.font": "Font: {value}",
    "diag.appearance": "Appearance: {theme}, character: {face}",
    "diag.target": "Daily goal: {t}",
    "diag.target.weight": "From body weight",
    "diag.target.default": "Default",
    "diag.interval": "Interval: {n} min",
    "diag.crash": "Crash log: {summary}",
    "diag.update": "Update check: {status}",
    "diag.write_fail": "Write failures: {n} in a row",
    "diag.repaired": "Settings reverted to defaults",
    "diag.file_missing": "Does not exist",
    "diag.file_error": "Read failed: {error}",
    "diag.file": "Data: {path} -> {stat}",
    "diag.file_actual": "Window reads: {path} -> {stat}",

    # --- crashlog / updates / typeface ---
    "crash.none": "None",
    "crash.has_records": "Has records ({size} bytes)",
    "crash.count": "{n} entries",
    "crash.read_fail": "Read failed",
    "crash.trimmed": "(Older entries trimmed due to file size limit)",
    "updates.disabled": "Disabled",
    "updates.checking": "Checking",
    "updates.ok": "OK",
    "updates.fail": "Failed",
    "typeface.using": "Using embedded {family}",
    "typeface.system": "Using system {family} (bundled font not loaded)",
    "typeface.missing": "Missing {names}",
    "typeface.load_fail": "Failed to load {names}",
    "typeface.fallback": "Fell back to {actual}",

    # --- Sound readme ---
    "sound.readme_name": "README.txt",
    "sound.readme_text": (
        "Custom Reminder Sounds\n\n"
        "You normally don't need this folder — use the 'Choose' button "
        "under Reminder Sound in Settings, and the file is copied here "
        "automatically. This note is for those who prefer placing files "
        "directly.\n\n"
        "Place a sound file in this folder with one of these names:\n\n"
        "    weak.wav        Plays after 15 min ignored (built-in: ascending)\n"
        "    collapsed.wav   Plays after 40 min ignored (built-in: descending)\n\n"
        "You can place just one; the other will keep using the built-in.\n"
        "Delete the file to revert to built-in — no settings change needed.\n\n"
        "Format: WAV only. Renaming mp3/m4a to .wav won't work — Settings "
        "will show 'Not WAV format'.\n\n"
        "Volume is determined by the file itself — the app cannot adjust it. "
        "Windows plays at system volume. The built-in sounds peak at 26% of "
        "full scale; use that as a reference.\n\n"
        "Built-in sounds are in the app folder under "
        "_internal\\assets\\sound\\ — copy them as templates.\n\n"
        "Each sound row in Settings has a 'Preview' button to test immediately.\n"
    ),
}

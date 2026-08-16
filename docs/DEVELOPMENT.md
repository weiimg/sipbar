# Sipbar 開發說明

[← 回 README](../README.md)

## 從原始碼執行

需要 Python 3.13。

```bash
git clone https://github.com/weiimg/sipbar.git
cd sipbar
pip install -r requirements.txt
run.bat
```

`run.bat` 以 `pythonw` 啟動，不保留 console 視窗。需要查看錯誤訊息時改用
`python src\island.py`。

執行只依賴 PySide6。重建字體、重畫圖示、跑完整測試另外裝
`pip install -r requirements-dev.txt`。

## 專案結構

版面只有一條規則：**產生器在 `tools/`，它們的產物在 `assets/` 或 `docs/`，
程式在 `src/`。** 字體、圖示、展示動畫都是產物，四個都不該手改。

| 位置 | 內容 |
|---|---|
| `src/island.py` | 正式版，動態島。唯一的入口 |
| `src/settings.py` | 設定的讀寫、體重與作息推導、開機自啟、資料清除 |
| `src/onboard.py` | 首次啟動的引導 |
| `src/stats_window.py` | 紀錄視窗與設定頁，只畫不算 |
| `src/dashboard.py` | 紀錄的統計計算，只算不畫 |
| `src/typeface.py` | 隨程式散布的字體：載入、驗證、產生 QFont |
| `src/theme.py`、`paintkit.py`、`motion.py`、`pixelface.py`、`menu.py` | 調色盤、繪圖工具、彈簧、像素杯、選單 |
| `assets/fonts/` | `WaterPet Sans TC` Bold + Medium，加兩份 OFL |
| `assets/icon.ico` | 應用程式圖示 |
| `tools/` | 上面那些產物的產生器 |
| `tests/` | `test_*.py` 會回傳 exit code，`render_*.py` 是用眼睛驗的 |

## 建置

```bash
python tools/build_exe.py        # onedir、onefile，與發布用的 zip
python tools/build_font.py       # 合成 assets/fonts 的兩個 OTF
python tools/make_icon.py        # 產生 assets/icon.ico 與 docs/icon.png
python tools/make_demo.py        # 產生 docs/demo.webp
python tools/make_feature_icons.py   # 產生 README 功能區的四個圖示
python tools/time_launch.py      # 量 onefile 與 onedir 的啟動時間
```

## 測試

從專案根目錄執行，例如 `python tests/test_island.py`。

會回傳 exit code 的有 `test_island`、`test_streak`、`test_spring`、
`test_settings`、`test_copy_style`、`test_font_build`、`test_font_memory`。
`test_font_memory` 跑得慢，它開四個子行程量真實記憶體。
`test_peek_live` 會搶走滑鼠游標。

## 發版

步驟固定在[發版清單](RELEASE.md)，照著走不要靠記憶。版本號只寫在
`src/settings.py` 的 `VERSION`，其餘全部從它推導。

每版改了什麼寫進[更新紀錄](CHANGELOG.md)。

## 設計與決策

每個決定的理由，以及過程中判斷錯的地方，寫在[設計與決策](DESIGN.md)。

上架之前的完整開發日誌在 `notes/`，那份不進版本庫（內有個人資料），已於
2026-08-17 凍結。之後的過程紀錄用 GitHub issues 與 commit。

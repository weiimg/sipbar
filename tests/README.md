# 測試與渲染腳本

這些原本在 session 的暫存區，session 結束就會消失，所以搬進專案保存。

全部從專案根目錄執行，例如：

```bash
python tests/test_island.py
```

## 邏輯測試（會回傳 exit code，全過才是 0）

| 腳本 | 內容 |
|---|---|
| `test_island.py` | 島的 21 組：提醒時機、閒置不計時、升級、達標、換日、暫停、跨重啟接續、探頭、遮罩與視窗尺寸、文字寬度、延遲動畫的取消 |
| `test_streak.py` | 連續天數 11 組：累積、拍攝日跳過、護盾抵用、跨月重置、逐日遞增 |
| `test_spring.py` | 彈簧 8 組：過衝幅度、收斂時間、被打斷時的連續性、掉幀保護 |
| `test_settings.py` | 設定：體重換算、作息推導、舊鍵升級、設定檔遷移、齒輪點擊區、**改設定不重置倒數**、**捲動區不能是透明的洞**、換主題要連外框一起換 |
| `test_copy_style.py` | 介面文案的風格檢查：第二人稱、口語連接、語助詞 |
| `test_font_memory.py` | 字體序列的記憶體代價。**跑得慢**（開四個子行程），但擋的是一個 +523MB 的回歸 |
| `test_peek_live.py` | 頂端探頭實測。**會搶走滑鼠游標**，你同時在用滑鼠時會標記略過而非失敗 |

`test_font_memory.py` 不能用 `QT_QPA_PLATFORM=offscreen` 跑——offscreen 不會真的
把文字畫出來，兩組都會量到「很省」的假通過。它自己開子行程並跑真的事件迴圈，
就是為了避開這件事。

## ⚠ 會寫檔的測試一定要先架沙箱

`test_settings.py` 會呼叫 `SettingsPage._emit()`，而那會 `save_config()`。
沒有沙箱的話它寫的是**使用者真實的** `%LOCALAPPDATA%\WaterPet\config.json`——
跑一次測試就把人家調好的設定洗成測試預設值，而且測試全綠、沒有任何錯誤訊息。

這件事真的發生過（目標 10 次 / 間隔 45 分被洗成 7 次 / 60 分）。現在該檔開頭會把
`settings` 模組的所有路徑改指到暫存目錄，第 8b 節是這道沙箱的看門狗。
**日後新增任何會寫檔的測試，先確認它寫到哪裡。**

## 渲染驗證（產圖，要用眼睛看）

| 腳本 | 產出 |
|---|---|
| `render_final.py` | 島的各狀態對照 |
| `render_stats_window.py` | 紀錄視窗三頁定格，**並驗證每頁高度放得下** |
| `render_settings.py` | 設定頁定格（有填／沒填體重兩種），**並驗證內容放得下** |
| `render_both.py` | 紀錄視窗「剛開始（稀疏）」與「用了一陣子（豐富）」兩種狀態 × 三頁 |
| `render_anim.py` | 視窗進場動畫逐幀 |
| `render_ring.py` | 今日環在各種數值下的排版 |
| `gen_dashboard.py` | 產 38 天擬真假資料，供上面幾支使用 |

**跑渲染前先跑 `gen_dashboard.py`**，它會在同目錄產生 `wp_dash/events.jsonl`。

## 字型調查（要再動字型時的依據）

| 腳本 | 內容 |
|---|---|
| `probe_text.py` | 量測次像素渲染是否作用（推翻了「半透明視窗只能灰階抗鋸齒」的說法） |
| `compare_engines.py` + `render_engine.py` | 三種字型引擎 × 三種字型的對照圖 |
| `small_text.py` | 小字的 hinting／字重／字級／對比變體比較 |
| `font_ab.py` | 換字型前後對照 |

## Lottie 素材探測（Phase 0／1）

| 腳本 | 內容 |
|---|---|
| `lottie_probe.py` | 給它任意 `.json`，輸出單幀耗時、alpha 檢查、水位曲線、膠捲圖 |
| `make_probe_lottie.py` | 產生 `water_probe.json` / `water_heavy.json` 兩個探測素材 |

```bash
python tests/lottie_probe.py tests/water_probe.json
```

Phase 1 挑素材時，把下載的候選檔直接丟給它，看產出的 `<名稱>_strip.png`。
**判準不是動畫好不好看，是停在中間某一幀讀不讀得出水位。**

需要 `pip install rlottie-python`（381KB wheel，免編譯）。

**這裡有個坑**：`LottieAnimation.from_file()` 在含中文的路徑下會靜默失敗
（不丟例外，回 0 幀空動畫），本專案的路徑就有中文。一律用 `from_data()` 自己讀檔。

## 已知限制

腳本裡的專案路徑是寫死的絕對路徑（`sys.path.insert`）。專案搬家的話要一起改。
產出的圖與暫存資料會落在腳本所在的目錄下。

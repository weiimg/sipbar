# Sipbar 發版清單

[← 回 README](../README.md)

照著這份走，不要靠記憶。跳過任何一項都請在 release notes 裡說明。
建置細節見[開發說明](DEVELOPMENT.md)，每版改了什麼寫在[更新紀錄](CHANGELOG.md)。

## 先決定走哪一條

| | 熱修線 | 常規線 |
|---|---|---|
| **什麼情況** | 裝不起來、資料壞掉、一開就閃退 | 其餘全部 |
| **版本號** | 修訂號 `0.9.1` | 次版本 `0.10.0` |
| **範圍** | **只修那一件事**，不夾帶任何其他改動 | 一批，開工前鎖死 |
| **時機** | 不排隊，修完立刻發 | 照節奏 |

常規線開工時先把要做的 issue 挑進 milestone，挑完就封口。中途新來的一律進下一輪，
熱修除外——**沒有鎖範圍的話，單人專案的一輪會無限延長。**

---

## 一、改版本號

只有一個地方要改：

```
src/settings.py   VERSION = "0.9.0-beta"
```

其餘全部從它推導——`tools/build_exe.py` 用正規表示式讀它去生 `build/version_info.txt`，
紀錄視窗的「版本」欄讀 `settings.VERSION`，島的 `greeted_version` 也是。
**不要在別的地方另外寫一次版本號。**

## 二、更新 CHANGELOG

把 `docs/CHANGELOG.md` 的「未發布」整段搬到新的版本標題底下，補上日期。
「未發布」保留空的，給下一輪用。

寫使用者感覺得到的變化，不要寫 commit。

## 三、跑測試

從專案根目錄執行。會回傳 exit code 的有這七個：

```bash
python tests/test_island.py && python tests/test_streak.py && python tests/test_spring.py && python tests/test_settings.py && python tests/test_copy_style.py && python tests/test_font_build.py && python tests/test_font_memory.py
```

`test_font_memory` 跑得慢，它開四個子行程量真實記憶體。
`test_peek_live` **不要**放進這串，它會搶走滑鼠游標。

`render_*.py` 是用眼睛驗的，改過版面才需要跑。

## 四、建置

**建置之前先把跑著的 Sipbar 關掉，包含從原始碼跑的那種。**

沒關的話 PyInstaller 會在清理暫存目錄時失敗，訊息長這樣：

```
PermissionError: [WinError 5] 存取被拒。: ...\build\onedir\Sipbar\localpycs
FAIL PyInstaller 失敗（onedir）
```

那個 `localpycs` 是 PyInstaller 這一輪自己剛建出來、然後刪不掉的，
所以看起來像殘留檔案的問題——**手動刪掉 `build/` 與 `dist/` 再跑一次沒有用，
會停在同一個地方**。2026-08-20 發 0.10.1 時卡在這裡三次才找到原因。

```bash
python tools/build_exe.py
```

會產出三樣東西：

| 產物 | 位置 |
|---|---|
| onedir（解壓即用，發布的就是這個） | `dist/onedir/Sipbar/` |
| onefile（單一 exe，每次啟動要解到 `%TEMP%`） | `dist/onefile/Sipbar.exe` |
| 發布用 zip | `dist/Sipbar-{版本}-portable.zip` |

## 五、實機驗一遍

**在乾淨的路徑解壓縮測試，不要在專案資料夾裡跑。** 至少確認：

- [ ] 解壓縮後雙擊 `Sipbar.exe` 起得來
- [ ] 啟動時島會自己滑下來打招呼
- [ ] 滑鼠移到螢幕頂端中央叫得出島
- [ ] 左鍵記錄補水、右鍵開得了選單
- [ ] 系統匣圖示在，右鍵選單正常
- [ ] 喝水紀錄視窗三個分頁都開得起來
- [ ] 設定頁的「開機時啟動」開得起來也關得掉
- [ ] **`%LOCALAPPDATA%\Sipbar\` 裡沒有夾帶你自己的 `config.json`**

最後一項特別重要：`.gitignore` 擋的是版本庫，擋不住打包。真的混進去的話，
每個新使用者一裝就繼承你的體重與作息設定，而且沒有任何提示。

## 六、發布

```bash
git tag v0.9.0-beta
git push origin main --tags
gh release create v0.9.0-beta dist/Sipbar-0.9.0-beta-portable.zip --title "v0.9.0-beta" --notes-file <release notes 檔案>
```

正式版拿掉 `--prerelease`；beta 要加。

Release notes 至少要有：下載連結與檔案大小、系統需求、**SmartScreen 那段說明**、
資料存放位置、已知限制，以及 **zip 的 SHA256**。

雜湊在 `build_exe.py` 跑完時就印出來了，直接複製那一行。它是下載的人唯一能
確認「拿到的是不是原本那一份」的辦法——exe 沒有數位簽章，而簽章憑證要年費。
Release notes 裡順手附上驗法：

```
Get-FileHash .\Sipbar-x.y.z-portable.zip -Algorithm SHA256
```

0.9.0-beta 那篇可以直接拿來改：

```bash
gh release view v0.9.0-beta --json body -q .body
```

## 七、發完之後

- [ ] 從 Releases 頁面**重新下載一次**，確認 zip 沒壞、檔名與版本號對得上
- [ ] milestone 關掉，沒做完的 issue 移到下一個
- [ ] 頭 48–72 小時盯著 issues。第一批最可能收到的是：SmartScreen／防毒誤判、
      高 DPI 縮放下島的位置或大小跑掉、找不到系統匣圖示

---

## 版本號怎麼選

照 [SemVer](https://semver.org/lang/zh-TW/)：

- **修訂號**（0.9.**1**）— 只修 bug，行為不變
- **次版本**（0.**10**.0）— 加功能，舊資料照樣讀得動
- **主版本**（**1**.0.0）— 破壞既有資料或行為。**動到 `events.jsonl` 或
  `config.json` 的結構就是這一級**，而且要寫遷移程式，參考 `settings.py` 的
  `_migrate_data_dir()`／`_migrate_autostart()`

`-beta` 後綴代表還在收回饋、介面可能再改。拿掉它等於宣告「這個介面我打算維持」。

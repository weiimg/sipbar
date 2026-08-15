# 隨附字體

| 檔案 | 字重 | 用在哪 |
|---|---|---|
| `WaterPetSansTC-Bold.otf` | 700 | display / title / section / headline |
| `WaterPetSansTC-Medium.otf` | 500 | body / caption、島的小標 |

Regular 400 沒有隨附——全專案沒有任何地方要求這個字重。

## 這是合成品，不要手改

**這兩個檔是建置產物**，由 `tools/build_font.py` 產生：Inter 的拉丁字形
（101 個碼位）寫進 Noto Sans TC 的 CFF，其餘 20,644 個字形原封不動。
要改就改建置腳本再重跑，直接編輯字體檔的話下次建置就被蓋掉了。

    python tools/build_font.py
    python tests/test_font_build.py

## 為什麼要合成一個檔，不是掛兩個字體

**只要 Qt 需要為任何一個字做字體回退，它就會把一整份中文字符表載進記憶體。**
實測島畫出文字之後的私有記憶體：

| 做法 | 記憶體 |
|---|---|
| 單一家族，自己蓋得住全部的字 | 56 MB |
| `setFamilies(["Inter", "Noto Sans TC"])` | 396 MB |
| 只掛 Inter，中文交給系統回退 | 394 MB |

貴的不是 Inter（2,849 個字符），是被迫整份載入的 Noto（20,745 個）。
完整的量測與其他做法的比較寫在 `tools/build_font.py` 的 docstring。

## 為什麼底是 Noto Sans TC

`typeface.py` 開頭有完整說明。一句話：Noto Sans TC 有真正的 Medium 500，
Microsoft JhengHei UI 沒有中間字重，而內文用 Medium 正是在補償半透明視窗吃不到
ClearType 造成的「字偏薄」。退回 JhengHei UI 等於把已經解掉的問題靜默放回來。

## 授權

成品衍生自兩個字體，**兩個都是 SIL Open Font License 1.1**：

| 來源 | 取自 | 授權全文 |
|---|---|---|
| Noto Sans TC | [notofonts/noto-cjk](https://github.com/notofonts/noto-cjk) 的 `Sans/LICENSE` | `OFL.txt` |
| Inter | [google/fonts](https://github.com/google/fonts) 的 `ofl/inter` | `Inter-OFL.txt` |

兩份授權的著作權行都**沒有宣告 Reserved Font Name**，所以衍生字體可以散布。
即使如此仍然改名為 `WaterPet Sans TC`：成品既不是 Inter 也不是 Noto Sans TC，
掛著任一個原名都是在誤導。

OFL 的條件：

1. **散布時必須附上授權條文全文** — 這兩個 `*-OFL.txt` 要跟著字體一起走，
   打包成 exe 時也要收進去
2. 不得單獨販售字體本身
3. 衍生物必須同樣以 OFL 散布

> 授權條文只能原封照抄，不要重打、翻譯或摘要。要更新就重新從上游取得。

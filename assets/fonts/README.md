# 隨附字體

| 檔案 | 字重 | 用在哪 |
|---|---|---|
| `NotoSansTC-Bold.otf` | 700 | display / title / section / headline |
| `NotoSansTC-Medium.otf` | 500 | body / caption、島的小標 |

Regular 400 沒有隨附——全專案沒有任何地方要求這個字重。

## 為什麼要內嵌

`typeface.py` 開頭有完整說明。一句話：Noto Sans TC 有真正的 Medium 500，
Microsoft JhengHei UI 沒有中間字重，而內文用 Medium 正是在補償半透明視窗吃不到
ClearType 造成的「字偏薄」。退回 JhengHei UI 等於把已經解掉的問題靜默放回來。

## 授權

Noto Sans TC 採用 **SIL Open Font License 1.1**，全文見同資料夾的 `OFL.txt`
（取自上游 [notofonts/noto-cjk](https://github.com/notofonts/noto-cjk) 的 `Sans/LICENSE`，
4,303 bytes、純 ASCII、未經任何改寫）。

這個授權允許隨軟體散布（含商用與閉源），條件是：

1. **散布時必須附上授權條文全文** — `OFL.txt` 要跟著字體一起走，打包成 exe 時也要收進去
2. 不得單獨販售字體本身
3. 修改後的版本不得沿用保留字型名稱（Reserved Font Name）

> 授權條文只能原封照抄，不要重打、翻譯或摘要。要更新就重新從上游取得。

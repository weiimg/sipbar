# 建置字體用的來源

`build_font.py` 的輸入，**不是隨程式散布的東西**（那是 `assets/fonts/`）。

| 檔案 | 來源 |
|---|---|
| `Inter[opsz,wght].ttf` | [google/fonts](https://github.com/google/fonts) 的 `ofl/inter`，可變字體，opsz 14–32／wght 100–900 |
| `NotoSansTC-Medium.otf`、`NotoSansTC-Bold.otf` | [notofonts/noto-cjk](https://github.com/notofonts/noto-cjk) 的靜態 OTF |

**這些檔案跟著版本庫走**（約 12MB），不靠下載。Google Fonts 現在只提供 Inter 的
可變字體、Noto Sans TC 的靜態 OTF 也已經不在同一個位置，改成隨用隨抓的話，
哪天上游換了檔名或格式，建置就再也重現不出同一份成品。

建置需要 `fonttools`（只有建置需要，跑程式不需要）：

    pip install fonttools

授權都是 SIL OFL 1.1，見 `assets/fonts/` 裡的兩份 `*-OFL.txt`。

<div align="center">

<img src="docs/demo.webp" width="464" alt="動態島從螢幕頂端滑下來，游標點一下，杯子變綠、進度多一格，然後滑回去">

<img src="docs/icon.png" width="64" alt="">

# Sipbar

**Take a sip, even in the flow**

[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
![platform](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6)
[![release](https://img.shields.io/badge/下載-v0.9.0--beta-success)](https://github.com/weiimg/sipbar/releases/latest)

</div>

工作再忙，也記得喝點水。

Sipbar 平常不會出現在螢幕上，時間到才從頂端滑下來。點一下就記錄，
不管喝幾口都算。

## 系統需求

- Windows 10 或 11
- 不用先裝 Python 或任何其他東西

## 下載與安裝

1. 到 [Releases](https://github.com/weiimg/sipbar/releases/latest) 下載
   `Sipbar-0.9.0-beta-portable.zip`
2. 解壓縮到你喜歡的位置
3. 執行裡面的 `Sipbar.exe`

第一次執行時 Windows 會跳「已保護您的電腦」。點**其他資訊**，再點**仍要執行**。
Windows 對所有沒有數位簽章的程式都會這樣。

## 怎麼用

| 動作 | 結果 |
|---|---|
| 滑鼠移到螢幕頂端中央 | 叫它出來，不用等提醒 |
| 左鍵點島 | 記錄補水一次 |
| 滑鼠移到島上 | 展開看完整訊息 |
| 右鍵點島 | 選單：記錄補水、暫停 2 小時、喝水紀錄、設定、結束程式 |
| 系統匣圖示 | 同樣的功能，左鍵補水、右鍵選單 |

五個狀態、資料存在哪、已知限制，見[使用說明](docs/USAGE.md)。

## 不想用了

關掉程式，把解壓縮出來的資料夾刪掉，再刪掉 `%LOCALAPPDATA%\Sipbar\`。
沒有安裝程式，也不會在系統裡留下東西。

## 給開發者

需要 Python 3.13。

```bash
git clone https://github.com/weiimg/sipbar.git
cd sipbar
pip install -r requirements.txt
run.bat
```

`run.bat` 以 `pythonw` 啟動，不保留 console 視窗。需要查看錯誤訊息時改用
`python src\island.py`。自己打包成執行檔用 `python tools/build_exe.py`。

設計與取捨的完整記錄在[設計與決策](docs/DESIGN.md)。

## 授權

程式碼採用 [MIT](LICENSE) 授權。隨附字體不在此範圍內，另依 SIL Open Font
License 1.1 散布，條件與來源見 [assets/fonts](assets/fonts/README.md)。

---

> 我的 side project，跟 Claude 一起寫的。我不是工程師，是接案的影像創作者，
> 做這個是因為我自己需要有東西提醒我喝水，做完覺得堪用就放上來。

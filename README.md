<div align="center">

<img src="docs/icon.png" width="72" alt="">

# Sipbar

**Take a sip, even in the flow**

[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
![python](https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white)
![platform](https://img.shields.io/badge/platform-Windows-0078D6)

<img src="docs/demo.webp" width="464" alt="動態島從螢幕頂端滑下來，游標點一下，杯子變綠、進度多一格，然後滑回去">

</div>

工作再忙，也記得喝點水。

Sipbar 平常不會出現在螢幕上，時間到才從頂端滑下來。點一下就記錄，
不管喝幾口都算。

## Requirements

Windows 10 / 11。不需要先裝 Python。

## Installation

到 [Releases](https://github.com/weiimg/sipbar/releases/latest) 下載
`Sipbar-0.9.0-beta-portable.zip`，解壓縮後執行 `Sipbar.exe`。不需要安裝。

第一次執行 Windows 會跳「已保護您的電腦」，點「其他資訊」再點「仍要執行」。
那是 SmartScreen 對沒有簽章的程式一律會跳的警告，不是偵測到問題。程式碼簽章
憑證一年要價數百美金，這是個人的 side project，沒有買。不放心的話原始碼全部
公開在這裡，可以自己從原始碼跑。

## Usage

平常它不在畫面上，時間到才自己滑下來。把滑鼠移到螢幕上緣中央可以隨時叫它出來。

完整的操作方式、五個狀態、資料位置與已知限制，見[使用說明](docs/USAGE.md)。

## From source

需要 Python 3.13。

```bash
git clone https://github.com/weiimg/sipbar.git
cd sipbar
pip install -r requirements.txt
run.bat
```

`run.bat` 以 `pythonw` 啟動，不保留 console 視窗。需要查看錯誤訊息時改用：

```bash
python src\island.py
```

自己打包成執行檔用 `python tools/build_exe.py`。

## License

程式碼採用 [MIT](LICENSE) 授權。隨附字體不在此範圍內，另依 SIL Open Font
License 1.1 散布，條件與來源見 [assets/fonts](assets/fonts/README.md)。

---

> 我的 side project，跟 Claude 一起寫的。我不是工程師，是接案的影像創作者，
> 做這個是因為我自己需要有東西提醒我喝水，做完覺得堪用就放上來。

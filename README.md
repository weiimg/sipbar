<div align="center">

<h1><img src="docs/icon.png" width="34" align="top" alt=""> Sipbar</h1>

**Take a sip, even in the flow**

[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
![platform](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6)
[![release](https://img.shields.io/github/v/release/weiimg/sipbar?include_prereleases&label=%E4%B8%8B%E8%BC%89&color=success)](https://github.com/weiimg/sipbar/releases/latest)

<img src="docs/demo.webp" width="464" alt="動態島從螢幕頂端滑下來，游標點一下，杯子變綠、進度多一格，然後滑回去">

&nbsp;

大家都知道要多喝水，但培養好習慣總是很難。

身體的水就交給 Sipbar 提醒，
喝個幾口，就能回去更專注的工作。

工作再忙，也記得喝點水。



---
[主要功能](#主要功能) • [下載與安裝](#下載與安裝) • [如何使用](#如何使用) • [解除安裝](#解除安裝)

</div>

&nbsp;

## 主要功能

<table>
<tr>
<td width="25%" align="center"><img src="docs/feat-hidden.png" width="80" alt=""><br>平常不佔你的畫面，該喝水時自動出現提醒</td>
<td width="25%" align="center"><img src="docs/feat-tap.png" width="80" alt=""><br>喝多喝少都不用算，點一下就幫你記錄</td>
<td width="25%" align="center"><img src="docs/feat-streak.png" width="80" alt=""><br>連續天數持續累積，沒開電腦不會中斷</td>
<td width="25%" align="center"><img src="docs/feat-rhythm.png" width="80" alt=""><br>根據你的體重與作息自動調整喝水次數</td>
</tr>
</table>

---

## 系統需求

- Windows 10 / 11

---

## 下載與安裝

1. 到 [Releases](https://github.com/weiimg/sipbar/releases/latest) 下載 zip
2. 解壓縮至目的地
3. 執行 `Sipbar.exe`

**若您是首次使用**

第一次執行時 Windows 會跳出「已保護您的電腦」。<br>
點**其他資訊**，再點**仍要執行**。<br>
Windows 對所有未經數位簽章的程式皆會顯示此提示。

&nbsp;

**若您已安裝過舊版**

1. 右鍵點動態島，選擇「結束程式」（滑鼠移到螢幕頂端中央可叫出動態島）
2. 解壓縮新版並執行

設定與紀錄存放於程式之外，會自動接上，不需要搬移。舊的資料夾確認新版可以正常
執行之後即可刪除。若您開啟過「開機時啟動」，新版會自動將它改指向自己。

---

## 如何使用

<table>
<tr><td>滑鼠移到螢幕頂端中央</td><td>呼叫動態島</td></tr>
<tr><td>左鍵點擊動態島</td><td>記錄補水一次</td></tr>
<tr><td>右鍵點擊動態島</td><td>展開功能選單</td></tr>
</table>

詳細內容請見 [使用說明](docs/USAGE.md)。

---

## 解除安裝

1. 若開啟過「開機時啟動」，先到設定頁將它關閉
2. 右鍵點動態島，選擇「結束程式」
3. 刪除解壓縮出來的資料夾
4. 刪除 `%LOCALAPPDATA%\Sipbar\`，設定與紀錄存放於此

第一步必須在刪除程式之前完成。此設定寫入 Windows 登錄檔，該筆記錄不會隨資料夾
一併移除。若已經刪除，開啟工作管理員的「啟動應用程式」分頁，將 Sipbar 停用即可。

---

## 授權

程式碼採用 [MIT](LICENSE) 授權。隨附字體不在此範圍內，另依 SIL Open Font
License 1.1 散布，條件與來源見 [assets/fonts](assets/fonts/README.md)。

自行建置、專案結構與設計取捨見[開發說明](docs/DEVELOPMENT.md)。

程式碰得到哪些東西、以及怎麼回報安全性問題，見[安全性說明](SECURITY.md)。

---

> 這是一項使用 Claude 撰寫的 side project。
> 做這個是因為我想玩玩看動態島的效果，而且我都不太喝水，需要一點提醒，做完覺得堪用就放上來。

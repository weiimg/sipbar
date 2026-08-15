@echo off
rem 正式版：動態島。用 pythonw 啟動，不留 console 視窗。
rem 第一次跑或出錯時改用：python island.py（才看得到錯誤訊息）
start "" pythonw "%~dp0island.py"

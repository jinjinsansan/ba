@echo off
REM LAPLACE COPILOT v2 ネイティブ GUI 起動
cd /d %~dp0

REM 古いバイトコードキャッシュ削除
if exist __pycache__ rmdir /s /q __pycache__

REM ネイティブウィンドウ起動 (pywebview)
REM ※ サーバ + ウィンドウが launcher.py 内で同時起動・連動終了
python -B launcher.py

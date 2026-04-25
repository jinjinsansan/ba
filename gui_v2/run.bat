@echo off
REM ================================================
REM  LAPLACE COPILOT v2 - ネイティブ GUI 起動
REM ================================================
cd /d %~dp0

REM 1. 古い Python が port 5050 を握っていたら kill (zombie 対策)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr "127.0.0.1:5050.*LISTENING"') do (
  echo [cleanup] kill old process PID %%a
  taskkill /F /PID %%a >nul 2>&1
)

REM 2. 古いバイトコードキャッシュ削除
if exist __pycache__ rmdir /s /q __pycache__

REM 3. ネイティブウィンドウ起動 (pywebview)
echo [launch] LAPLACE COPILOT v2 起動中...
python -B launcher.py

REM 4. ウィンドウ閉じたら一時停止 (エラー確認用)
echo.
echo [exit] ウィンドウが閉じられました
pause

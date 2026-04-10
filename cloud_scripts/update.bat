@echo off
REM LAPLACE 更新 + 再起動スクリプト (クラウドPC用)
REM ダブルクリックで:
REM 1. 既存のElectronプロセスを終了
REM 2. git pull で最新ソース取得
REM 3. GUIを再起動

echo ================================================
echo LAPLACE Update and Restart
echo ================================================

echo [1/3] Stopping existing Electron processes...
taskkill /F /IM electron.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2/3] Pulling latest from GitHub...
cd /d C:\dev\ba
"C:\Program Files\Git\cmd\git.exe" pull

echo [3/3] Starting GUI...
cd /d C:\dev\ba\gui
start "" npm run dev

echo.
echo Done! GUI should be starting now.
timeout /t 3 /nobreak >nul

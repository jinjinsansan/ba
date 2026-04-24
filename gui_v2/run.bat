@echo off
REM Laplace Copilot ba GUI v2 起動ランチャー
cd /d %~dp0
echo ============================================================
echo Laplace Copilot GUI v2 - ba
echo 起動後、ブラウザで http://127.0.0.1:5050 を開いてください
echo 停止は Ctrl+C
echo ============================================================
python app.py
pause

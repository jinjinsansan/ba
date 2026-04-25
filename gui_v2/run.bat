@echo off
REM Laplace Copilot ba GUI v2 起動ランチャー
cd /d %~dp0

REM 古いバイトコードキャッシュを削除 (コード変更を確実に反映)
if exist __pycache__ rmdir /s /q __pycache__

echo ============================================================
echo  Laplace Copilot GUI v2 - ba (Pragmatic Play)
echo  起動後ブラウザが自動で開きます
echo  停止は Ctrl+C
echo ============================================================

REM サーバー起動後にブラウザを開く
start /min "" cmd /c "ping -n 4 127.0.0.1 >nul & start \"\" \"http://127.0.0.1:5050\""

python -B app.py
pause

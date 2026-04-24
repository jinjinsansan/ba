@echo off
REM Laplace Copilot ba GUI v2 セットアップ
cd /d %~dp0
echo ============================================================
echo Laplace Copilot GUI v2 - セットアップ
echo ============================================================

echo.
echo Python バージョン確認...
python --version
if errorlevel 1 (
  echo [ERROR] Python がインストールされていません。
  echo https://www.python.org/downloads/ からインストールしてください。
  pause
  exit /b 1
)

echo.
echo [1/2] Flask をインストール...
python -m pip install --upgrade Flask
if errorlevel 1 (
  echo [ERROR] Flask インストール失敗
  pause
  exit /b 1
)

echo.
set /p INSTALL_PLAYWRIGHT="Playwright (ロビー スクレイパ用) もインストールしますか? [y/N]: "
if /i "%INSTALL_PLAYWRIGHT%"=="y" (
  echo [2/2] Playwright をインストール...
  python -m pip install playwright
  python -m playwright install chromium
) else (
  echo [2/2] Playwright スキップ ^(DB-based lobby のみ利用可^)
)

echo.
echo ============================================================
echo セットアップ完了
echo 起動: run.bat をダブルクリック
echo ============================================================
pause

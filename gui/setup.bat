@echo off
chcp 65001 > nul
echo.
echo  LAPLACE セットアップ
echo  ========================
echo.

:: OpenSSHクライアントのインストール（未インストールの場合のみ）
where ssh >nul 2>&1
if errorlevel 1 (
  echo  [INFO] OpenSSH クライアントをインストール中...
  powershell -Command "Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0" >nul 2>&1
  echo  [OK] OpenSSH クライアントをインストールしました
) else (
  echo  [OK] OpenSSH クライアントは導入済みです
)

:: SSH鍵の配置
set SSH_DIR=%USERPROFILE%\.ssh
set KEY_SRC=%~dp0laplace_vps
set KEY_DST=%SSH_DIR%\laplace_vps

if not exist "%KEY_SRC%" (
  echo  [エラー] laplace_vps ファイルが見つかりません。
  echo  このファイルと同じフォルダに laplace_vps を置いてください。
  pause
  exit /b 1
)

if not exist "%SSH_DIR%" mkdir "%SSH_DIR%"
copy /Y "%KEY_SRC%" "%KEY_DST%" > nul
echo  [OK] SSH鍵を配置しました: %KEY_DST%

:: パーミッション設定（Windows）
icacls "%KEY_DST%" /inheritance:r /grant:r "%USERNAME%:R" > nul 2>&1
echo  [OK] SSH鍵のアクセス権を設定しました

echo.
echo  セットアップ完了！
echo  LAPLACE.exe を起動してください。
echo.
pause

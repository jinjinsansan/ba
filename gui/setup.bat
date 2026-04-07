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

:: パーミッション設定（OpenSSH on Windows requires strict permissions）
powershell -Command "& { $k='%KEY_DST%'; $acl=Get-Acl $k; $acl.SetAccessRuleProtection($true,$false); $r=New-Object System.Security.AccessControl.FileSystemAccessRule('%USERNAME%','FullControl','Allow'); $acl.SetAccessRule($r); Set-Acl $k $acl }" > nul 2>&1
echo  [OK] SSH鍵のアクセス権を設定しました

:: SSH接続テスト
echo  [INFO] VPS接続を確認中...
ssh -i "%KEY_DST%" -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=10 laplace@210.131.215.116 "echo OK" > nul 2>&1
if errorlevel 1 (
  echo  [警告] VPS接続に失敗しました。ネットワーク環境を確認してください。
) else (
  echo  [OK] VPS接続確認済み
)

echo.
echo  セットアップ完了！
echo  LAPLACE.exe を起動してください。
echo.
pause

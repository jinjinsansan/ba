# LAPLACE / bacopy インフラ接続情報

本ファイルは **Claude Code / Droid / ユーザー本人** が接続先を即参照できるようにするための台帳です。
秘密鍵の内容は一切含めません (パス・フィンガープリントのみ)。

最終更新: 2026-04-22

---

## 1. VPS (LAPLACE 本番 + bacopy-api)

| 項目 | 値 |
|------|---|
| ホスト | `210.131.215.116` |
| ユーザー | `laplace` |
| ポート | `22` (標準) |
| OS | Ubuntu 25.04 / Python 3.13 |
| 接続鍵 (ローカルから) | `~/.ssh/laplace_vps` |
| 既登録鍵 (authorized_keys) | ED25519 `laplace-vps-droid`, ED25519 `droid` (Factory Droid 用, fingerprint `SHA256:28vG30Cs0+1DVXCYp7mckpDgd275AXsgxJfC5xF057k`) |
| 主要デプロイ先 | `/opt/laplace/`, `/opt/bacopy/`, `/opt/laplace2/monitor/` |
| 主要 systemd | `bacopy-api`, `laplace-api`, `laplace-pragmatic-collector`, `laplace-collector`, `laplace-crowd-collector` |
| 接続例 | `ssh -i ~/.ssh/laplace_vps laplace@210.131.215.116` |

### 用途別ディレクトリ
- `/opt/bacopy/` — bacopy-api + master UI (port 8010)
- `/opt/laplace/` — LAPLACE 本番 API + collector
- `/opt/laplace2/monitor/` — Pragmatic collector

---

## 2. Desktop Cloud (bafather — Xserver デスクトップクラウド)

| 項目 | 値 |
|------|---|
| ホスト | `162.43.83.54` |
| ユーザー | `Administrator` (ドメイン形式: `bafather\administrator`) |
| ポート | `22` |
| OS | Windows Server 2022 (ホスト名: `bafather`) |
| 接続鍵 (ローカルから) | `~/.ssh/laplace_vps` または `~/.ssh/xserver_key` |
| 既登録鍵 (`C:\ProgramData\ssh\administrators_authorized_keys`) | ED25519 `laplace-vps-droid`, RSA `user@DESKTOP-UH30MN6` (xserver_key 由来) |
| デフォルトシェル | PowerShell |
| 接続例 | `ssh -i ~/.ssh/laplace_vps Administrator@162.43.83.54` |

### 重要な注意点
- Windows OpenSSH で **管理者 (Administrators グループ)** のユーザーは、通常の `~/.ssh/authorized_keys` ではなく **`C:\ProgramData\ssh\administrators_authorized_keys`** を参照する。通常の場所に追加しても認証されない。
- `Add-Content` で追記する際は既存ファイル末尾の改行に注意 (最終行が改行なしだと次行と連結される)。2 行以上登録する時は `Set-Content -Value @($key1, $key2) -Encoding ASCII` で明示的に配列指定するのが安全。
- ファイル ACL は `SYSTEM:(F)` + `BUILTIN\Administrators:(F)` のみが正しい。他のユーザーに書き込み権限があると OpenSSH は鍵を拒否する。
- 接続後のシェルは PowerShell なので、`&&` は使えず `;` で区切る。詳細は `reference_desktop_cloud_ssh.md` (Claude memory) 参照。

### 配置済みファイル (GUI 本番運用機)
- `C:\Users\Administrator\Desktop\.env`
- `C:\Users\Administrator\Desktop\bacopy_executor_pragmatic_ws_live.py` (v0.5.0 系)
- `C:\Users\Administrator\Desktop\bacopy_db.py`
- `C:\Users\Administrator\Desktop\marubatsu_strategy.py`
- `C:\Users\Administrator\Desktop\copytrade_gui\` (Electron GUI)

### GUI 起動手順
RDP で接続 → PowerShell で:
```powershell
cd C:\Users\Administrator\Desktop\copytrade_gui
npm start
```
※ SSH セッションから `Start-Process` しても RDP 画面に見えない (別 Windows session)。必ず RDP で実行。

---

## 3. ローカル PC の SSH 鍵一覧

`~/.ssh/` (Windows: `%USERPROFILE%\.ssh\`) に存在する鍵:

| ファイル | 形式 | 用途 |
|----------|------|------|
| `laplace_vps` + `.pub` | ED25519 | **VPS / Desktop Cloud 両方**の主力鍵 |
| `xserver_key` + `.pub` | RSA 4096 | Xserver Desktop Cloud 専用 (コメント `user@DESKTOP-UH30MN6`) |
| `laplace_admin` + `.pub` | — | LAPLACE 管理者用途 (詳細は .pub コメント参照) |
| `laplace_tunnel_test` + `.pub` | — | reverse SSH tunnel テスト用 |
| `id_ed25519` / `id_rsa` + `.pub` | ED25519 / RSA | 汎用デフォルト鍵 |

`known_hosts` には `210.131.215.116` (VPS) と `162.43.83.54` (bafather) の両方が登録済。

**`~/.ssh/config` ファイルは存在しない** (Host エントリ管理なし)。必要なら各 `ssh` コマンドで `-i <鍵パス>` を明示する。

---

## 4. Droid (Factory.ai) 用接続設定

Droid は `DESKTOP-UH30MN6` (ユーザーのローカル PC) 上で動作する想定。

### VPS へ
- 鍵: Droid 自前の ED25519 (公開鍵は VPS `~/.ssh/authorized_keys` に登録済)
- fingerprint: `SHA256:28vG30Cs0+1DVXCYp7mckpDgd275AXsgxJfC5xF057k`
- 接続: `ssh laplace@210.131.215.116`

### Desktop Cloud (bafather) へ
- 鍵: `xserver_key` (既存のローカル鍵を流用)
- 公開鍵は `C:\ProgramData\ssh\administrators_authorized_keys` に登録済
- 接続: `ssh -i ~/.ssh/xserver_key Administrator@162.43.83.54`

### 登録済の Droid 公開鍵 (参照用)
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIF+wPCjyTA9qRkyRk0c6WQ/DlCz5r+6Rd/0JJA3+0o7c droid
```
(VPS のみに登録)

```
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDigHKs53GdC9RdqHYDndlrHBtNSCukzq3WWEBPpYsGLj8w/...== user@DESKTOP-UH30MN6
```
(VPS の `authorized_keys` と bafather の `administrators_authorized_keys` 両方に登録済)

---

## 5. セキュリティ原則

- **秘密鍵の中身をチャット / ドキュメント / リポジトリに貼らない**。パス・フィンガープリント・コメントまで。
- 新規 Droid セッションでも既存鍵 (`xserver_key`, `laplace_vps`) を流用可能。新しい鍵生成が必要な場合は公開鍵のみ受け取って登録する。
- `~/.ssh/authorized_keys` (VPS) / `administrators_authorized_keys` (bafather) に追記する際は **末尾改行** に注意 (前行と連結しないように)。事故ったら `Set-Content` で明示的に再書き込み。
- bafather 側は **`C:\ProgramData\ssh\administrators_authorized_keys`** を参照 (これが Windows OpenSSH の管理者用特殊パス)。`~\.ssh\authorized_keys` ではない。
- ACL は `SYSTEM:(F)` + `Administrators:(F)` のみに保つ。他ユーザーに権限があると OpenSSH は鍵を拒否。

---

## 6. 関連メモリ / ドキュメント

Claude Code の auto memory に以下のメモリあり (本ファイルはその公開版):
- `reference_vps_infra.md` — VPS 接続・systemd・DB 配置
- `reference_desktop_cloud_ssh.md` — Desktop Cloud (bafather) 接続手順
- `project_account_separation_incident.md` — 2026-04-21 hakudasama login-flood 事故記録 (復旧前の必須確認事項あり)
- `project_vps_hardening.md` — VPS systemd override + swap + cron 設定

これらは `C:\Users\USER\.claude\projects\E--dev-Cusor-bacopy\memory\` 配下にあり、通常 Droid からは直接参照できない。本 `INFRA.md` に要点を転記してある。

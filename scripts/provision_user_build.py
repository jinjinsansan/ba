"""LAPLACE ユーザー別 EXE ビルド用のサポートトンネル情報をプロビジョニング。

各エンドユーザー向けに:
  1. ed25519 鍵ペアを生成
  2. VPS 踏み台 (laplace_support@210.131.215.116) の authorized_keys に公開鍵を登録
  3. ユーザー固有の固定ポート番号を割り当て
  4. EXE にバンドルする .env と秘密鍵を gui/user_build/<slug>/ に配置

配布時のフロー:
  python scripts/provision_user_build.py --email alice@example.com
  → gui/user_build/alice_at_example_com/ が生成される
  → 後続の電子ビルドで extraResources に指定してパッケージング

Usage:
  # 新規プロビジョニング (自動で次の空きポート割当)
  python scripts/provision_user_build.py --email alice@example.com

  # ポート指定
  python scripts/provision_user_build.py --email alice@example.com --port 20042

  # 既存ユーザーを再発行 (鍵ローテーション) — 既存鍵は上書き
  python scripts/provision_user_build.py --email alice@example.com --rotate

  # 登録一覧を確認 (VPS の authorized_keys を表示)
  python scripts/provision_user_build.py --list

前提条件:
  - ローカルに ssh-keygen があること
  - VPS (laplace@210.131.215.116) に SSH で sudo NOPASSWD 可能なこと
  - 秘密鍵 ~/.ssh/laplace_vps があること
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- 設定 ---
REPO_ROOT = Path(__file__).resolve().parent.parent
USER_BUILD_DIR = REPO_ROOT / "gui" / "user_build"
REGISTRY_CSV = REPO_ROOT / "scripts" / "user_ports.csv"  # 管理者ローカルの台帳
# 環境変数で上書き可
_BASTION_HOST = os.environ.get("LAPLACE_BASTION_HOST", "210.131.215.116")
_BASTION_USER = os.environ.get("LAPLACE_BASTION_USER", "laplace")
VPS_SSH = f"{_BASTION_USER}@{_BASTION_HOST}"
VPS_KEY = Path(os.environ.get("LAPLACE_BASTION_KEY", str(Path.home() / ".ssh" / "laplace_vps")))
SUPPORT_USER_ON_VPS = os.environ.get("LAPLACE_SUPPORT_USER", "laplace_support")
SUPPORT_HOST = f"{SUPPORT_USER_ON_VPS}@{_BASTION_HOST}"
PORT_RANGE_START = 20001
PORT_RANGE_END = 29999

# authorized_keys 行のテンプレート (restrict で最小権限、permitopen で当該ポートのみ許可)
AUTHORIZED_KEY_TEMPLATE = (
    'restrict,port-forwarding,permitlisten="127.0.0.1:{port}",'
    'command="/bin/echo tunnel-only" {pubkey}'
)


def slugify_email(email: str) -> str:
    """email を安全なディレクトリ名に変換 (alice@example.com → alice_at_example_com)"""
    s = email.lower().strip()
    s = s.replace("@", "_at_")
    s = re.sub(r"[^a-z0-9_-]", "_", s)
    return s


def run_local(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def run_vps(remote_cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """VPS (laplace@) で任意のコマンドを実行"""
    cmd = [
        "ssh",
        "-i", str(VPS_KEY),
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        VPS_SSH,
        remote_cmd,
    ]
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def load_registry() -> list[dict]:
    if not REGISTRY_CSV.exists():
        return []
    with REGISTRY_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_registry(rows: list[dict]) -> None:
    """CSV を原子的に書き換える (tmp → rename)。同時実行の競合を最小化。"""
    REGISTRY_CSV.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_CSV.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["email", "port", "slug", "registered_at"])
        w.writeheader()
        w.writerows(rows)
    os.replace(str(tmp), str(REGISTRY_CSV))


def next_free_port(registry: list[dict]) -> int:
    used = {int(r["port"]) for r in registry if r.get("port")}
    for p in range(PORT_RANGE_START, PORT_RANGE_END + 1):
        if p not in used:
            return p
    raise RuntimeError("No free port in range")


def generate_keypair(user_dir: Path, comment: str) -> tuple[Path, Path]:
    priv = user_dir / "support_key"
    pub = user_dir / "support_key.pub"
    if priv.exists() or pub.exists():
        raise FileExistsError(f"Key already exists: {priv}. Use --rotate to regenerate.")
    user_dir.mkdir(parents=True, exist_ok=True)
    run_local(["ssh-keygen", "-t", "ed25519", "-f", str(priv), "-N", "", "-C", comment])
    # Windows では chmod が効かないが試みる
    try:
        os.chmod(priv, 0o600)
    except Exception:
        pass
    return priv, pub


def register_pubkey_on_vps(pubkey_content: str, port: int, email: str) -> None:
    """laplace_support の authorized_keys に行追加 (重複チェック付き)"""
    line = AUTHORIZED_KEY_TEMPLATE.format(port=port, pubkey=pubkey_content.strip())
    # 既存エントリにユーザーメール/ポートがあれば削除してから追加 (冪等化)
    sed_cmd = (
        f"sudo sed -i '/# user:{email}$/,/{re.escape(email)}$/d' "
        f"/home/{SUPPORT_USER_ON_VPS}/.ssh/authorized_keys 2>/dev/null || true"
    )
    run_vps(sed_cmd, check=False)
    # 追記
    append_cmd = (
        f"echo '# user:{email}' | sudo tee -a /home/{SUPPORT_USER_ON_VPS}/.ssh/authorized_keys > /dev/null && "
        f"echo '{line}' | sudo tee -a /home/{SUPPORT_USER_ON_VPS}/.ssh/authorized_keys > /dev/null && "
        f"sudo chown {SUPPORT_USER_ON_VPS}:{SUPPORT_USER_ON_VPS} /home/{SUPPORT_USER_ON_VPS}/.ssh/authorized_keys && "
        f"sudo chmod 600 /home/{SUPPORT_USER_ON_VPS}/.ssh/authorized_keys"
    )
    run_vps(append_cmd)


def remove_user_from_vps(email: str) -> None:
    sed_cmd = (
        f"sudo sed -i '/# user:{email}$/,+1d' "
        f"/home/{SUPPORT_USER_ON_VPS}/.ssh/authorized_keys"
    )
    run_vps(sed_cmd, check=False)


def write_user_env(user_dir: Path, email: str, port: int) -> Path:
    """EXE にバンドルする .env (既存 .env と合流するようサポート項目のみ)"""
    env_path = user_dir / "support.env"
    lines = [
        f"# LAPLACE Support Tunnel (per-user, auto-generated)",
        f"# user: {email}",
        f"# generated: {datetime.now(timezone.utc).isoformat()}",
        f"LAPLACE_SUPPORT_ENABLED=1",
        f"LAPLACE_SUPPORT_SSH_HOST={SUPPORT_HOST}",
        f"LAPLACE_SUPPORT_SSH_KEY=./support_key",
        f"LAPLACE_SUPPORT_REMOTE_PORT={port}",
        f"LAPLACE_SUPPORT_LOCAL_PORT=22",
        "",
    ]
    env_path.write_text("\n".join(lines), encoding="utf-8")
    return env_path


def cmd_provision(email: str, port: int | None, rotate: bool) -> None:
    registry = load_registry()
    slug = slugify_email(email)
    existing = next((r for r in registry if r["email"] == email), None)

    if existing:
        if rotate:
            # 既存鍵を削除して再生成
            user_dir = USER_BUILD_DIR / existing["slug"]
            for f in ("support_key", "support_key.pub"):
                p = user_dir / f
                if p.exists():
                    p.unlink()
            print(f"[rotate] Removed old keys for {email}")
            port_to_use = int(existing["port"])
        else:
            raise SystemExit(
                f"[abort] {email} is already provisioned (port={existing['port']}, slug={existing['slug']}).\n"
                f"Use --rotate to regenerate keys (port stays)."
            )
    else:
        port_to_use = port if port else next_free_port(registry)
        if any(int(r["port"]) == port_to_use for r in registry):
            raise SystemExit(f"[abort] Port {port_to_use} already in use")

    user_dir = USER_BUILD_DIR / slug
    priv, pub = generate_keypair(user_dir, comment=f"laplace_support:{email}")
    pubkey = pub.read_text(encoding="utf-8").strip()
    print(f"[ok] Keypair generated: {priv}")

    register_pubkey_on_vps(pubkey, port_to_use, email)
    print(f"[ok] Registered on VPS laplace_support authorized_keys (port={port_to_use})")

    env_path = write_user_env(user_dir, email, port_to_use)
    print(f"[ok] Env fragment written: {env_path}")

    # 台帳更新
    if existing:
        existing["registered_at"] = datetime.now(timezone.utc).isoformat()
    else:
        registry.append({
            "email": email,
            "port": str(port_to_use),
            "slug": slug,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        })
    save_registry(registry)
    print(f"[ok] Registry updated: {REGISTRY_CSV}")

    print("\n=== Provisioning complete ===")
    print(f"Email: {email}")
    print(f"Slug:  {slug}")
    print(f"Port:  {port_to_use}")
    print(f"Dir:   {user_dir}")
    print("\nNext: include the following in your EXE build extraResources:")
    print(f'  {{ "from": "gui/user_build/{slug}/support_key", "to": "support_key" }}')
    print(f'  {{ "from": "gui/user_build/{slug}/support.env", "to": "support.env" }}')


def cmd_list() -> None:
    registry = load_registry()
    print(f"Registered users ({len(registry)}):")
    for r in registry:
        print(f"  {r['email']:30s} port={r['port']} slug={r['slug']} at={r['registered_at']}")
    print(f"\nVPS authorized_keys:")
    res = run_vps(f"sudo cat /home/{SUPPORT_USER_ON_VPS}/.ssh/authorized_keys 2>&1 | head -n 40")
    print(res.stdout)


def cmd_revoke(email: str) -> None:
    registry = load_registry()
    existing = next((r for r in registry if r["email"] == email), None)
    if not existing:
        raise SystemExit(f"[abort] {email} not found in registry")
    remove_user_from_vps(email)
    registry = [r for r in registry if r["email"] != email]
    save_registry(registry)
    user_dir = USER_BUILD_DIR / existing["slug"]
    print(f"[ok] Revoked {email} (port={existing['port']}).")
    print(f"     User dir still at {user_dir} (manually delete if needed)")


def main() -> None:
    ap = argparse.ArgumentParser(description="LAPLACE support tunnel user provisioning")
    ap.add_argument("--email", help="User email")
    ap.add_argument("--port", type=int, help="Specific port (default: auto-assign)")
    ap.add_argument("--rotate", action="store_true", help="Regenerate keys for existing user")
    ap.add_argument("--list", action="store_true", help="List registered users")
    ap.add_argument("--revoke", action="store_true", help="Revoke user access (requires --email)")
    args = ap.parse_args()

    if args.list:
        cmd_list()
        return
    if args.revoke:
        if not args.email:
            ap.error("--revoke requires --email")
        cmd_revoke(args.email)
        return
    if not args.email:
        ap.error("--email required (or use --list)")
    cmd_provision(args.email, args.port, args.rotate)


if __name__ == "__main__":
    main()

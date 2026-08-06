-- サブスク+ウォレット突合モデル移行 (2026-08-06)
-- 新料金モデル: サブスク $200/30日(登録日起算・GUI利用の唯一のロック条件)
--             + 利益シェア 30% 週次(既存 weekly_pnl 基盤を全員に適用)
--             + ウォレット突合 案A(ウォッチオンリー: ユーザー自身のアドレスを登録し観測)
-- ※ Supabase SQL Editor に丸ごと貼り付けて Run。idempotent。
-- ※ 最下部「ロールアウト」ブロックはコメントアウト済み。切替日にオーナーが手動で実行する。

-- 1) billing.expires_at — サブスク期限。/api/auth/license が既に期限切れを拒否する。
--    (本番には既に存在する想定だが、環境差異に備えて冪等に追加)
alter table public.billing add column if not exists expires_at timestamptz;

-- 2) crypto_payments.kind に 'subscription' を許可
alter table public.crypto_payments drop constraint if exists crypto_payments_kind_check;
alter table public.crypto_payments add constraint crypto_payments_kind_check
  check (kind in ('license', 'charge', 'subscription'));

-- 3) wallets — ユーザー登録ウォレット(1ユーザー1アドレス・案A)
create table if not exists public.wallets (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references public.profiles(id) on delete cascade,
  network       text not null check (network in ('tron', 'bsc')),
  address       text not null,
  -- pending: 登録直後(オンチェーンでまだ動きを観測していない)
  -- verified: 最初の転送を観測済み(アドレス実在・所有の推定確認)
  status        text not null default 'pending' check (status in ('pending', 'verified')),
  -- 突合ステータス(ダッシュボード表示用): checking / matched / mismatched
  -- ※ mismatched への遷移は Phase 2(ベットPnLとの突合)で実装。Phase 1 は
  --    転送観測なし=checking / 観測あり=matched(TODO: 差異検知)
  recon_status  text not null default 'checking' check (recon_status in ('checking', 'matched', 'mismatched')),
  last_checked_at timestamptz,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
-- 1ユーザー1アドレス+アドレスの重複禁止(inline unique はエディタ貼り付けで
-- 壊れやすかったため独立文に分離 — ON CONFLICT / 23505 判定はどちらでも動く)
create unique index if not exists wallets_user_uniq on public.wallets (user_id);
create unique index if not exists wallets_address_uniq on public.wallets (address);
alter table public.wallets enable row level security;
drop policy if exists wallets_admin_all on public.wallets;
create policy wallets_admin_all on public.wallets for all to service_role using (true) with check (true);
drop policy if exists wallets_own_select on public.wallets;
create policy wallets_own_select on public.wallets for select using (auth.uid() = user_id);
-- insert/update はサーバー(service_role)経由のみ。変更にサポート確認が必要なため
-- ユーザー直接の update ポリシーは作らない。

-- 4) chain_transfers — 登録ウォレットのオンチェーン転送履歴(USDT のみ観測)
create table if not exists public.chain_transfers (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references public.profiles(id) on delete cascade,
  wallet_id     uuid not null references public.wallets(id) on delete cascade,
  network       text not null check (network in ('tron', 'bsc')),
  tx_hash       text not null,
  direction     text not null check (direction in ('in', 'out')),  -- ユーザーウォレット視点
  counterparty  text not null,
  amount_usdt   numeric(18,6) not null,
  occurred_at   timestamptz not null,
  -- stake_deposit: ユーザーウォレット → Stake(=カジノへの入金)
  -- stake_withdrawal: Stake → ユーザーウォレット(=カジノからの出金)
  -- other: それ以外(取引所・個人間送金など)
  classified    text not null default 'other' check (classified in ('stake_deposit', 'stake_withdrawal', 'other')),
  created_at    timestamptz not null default now()
);
create unique index if not exists chain_transfers_tx_uniq
  on public.chain_transfers (network, tx_hash, direction, counterparty);
create index if not exists chain_transfers_user_idx on public.chain_transfers (user_id, occurred_at desc);
alter table public.chain_transfers enable row level security;
drop policy if exists chain_transfers_admin_all on public.chain_transfers;
create policy chain_transfers_admin_all on public.chain_transfers for all to service_role using (true) with check (true);
drop policy if exists chain_transfers_own_select on public.chain_transfers;
create policy chain_transfers_own_select on public.chain_transfers for select using (auth.uid() = user_id);

-- 5) 新規ユーザーの利益シェア既定を 30% に
alter table public.billing alter column profit_share_rate set default 0.30;

-- ============================================================================
-- ロールアウト(切替日にオーナーが手動実行 — 経過措置のため自動では流さない)
-- ============================================================================
-- 新モデル = 「日次チャージ課金なし + 週次30% + サブスク期限ゲート」。
-- 既存の weekly_pnl cron は is_free=true のユーザーを週次課金対象にするので、
-- 全員 is_free=true + rate 30% にすれば設定だけで新モデルに切り替わる(コード変更不要)。
--
-- -- (a) 全ユーザーを週次30%へ(課金免除を維持したいユーザーは rate=0 で個別調整)
-- update public.billing set profit_share_rate = 0.30, is_free = true, updated_at = now();
--
-- -- (b) 既存アクティブユーザーにサブスク開始日を設定(例: 切替日から30日の猶予)
-- update public.billing set expires_at = now() + interval '30 days', updated_at = now()
--   where bot_paid = true and expires_at is null;
--
-- -- (c) 完全無料ユーザー(れいじ等)は期限なしのまま(expires_at null = 無期限)
--      必要なら admin/users で個別に expires_at を消す。

-- ============================================================
-- 受け子の BET 履歴 (2026-09-22・ダッシュボード段階2)
--
-- 受け子 GUI が「Stake が受理して決済された勝負」を1件ずつ POST /api/receiver/bets へ送り、ここに残す。
-- 会員ページ (/me/bets) と管理画面 (ユーザー詳細の BET タブ) が読む。
-- まず田辺版 (BACOPY) の GUI から。梶原版・韓国版は各マスターの決済記録から取り込む予定。
-- 同じ勝負を二重に数えないよう、GUI が付ける client_id で (user_id, client_id) を一意にする。
-- 冪等。
-- ============================================================

create table if not exists public.receiver_bets (
  id           bigserial primary key,
  user_id      uuid not null references auth.users(id) on delete cascade,
  product      text not null check (product in ('bacopy', 'kbjapan', 'kbkorea')),
  executor_id  text not null default '',
  client_id    text not null,
  occurred_at  timestamptz not null,
  table_name   text,
  side         text,            -- 'player' / 'banker' / 'tie'
  amount       numeric(18,6),
  result       text,            -- 'player' / 'banker' / 'tie' (出た結果)
  outcome      text not null check (outcome in ('win', 'lose', 'push')),
  pnl          numeric(18,6),
  balance_after numeric(18,6),
  source       text not null default 'gui',
  created_at   timestamptz not null default now(),
  unique (user_id, client_id)
);

create index if not exists idx_receiver_bets_user_time on public.receiver_bets(user_id, occurred_at desc);
create index if not exists idx_receiver_bets_time on public.receiver_bets(occurred_at desc);

-- 読み書きはサーバー (service role) だけ。
alter table public.receiver_bets enable row level security;

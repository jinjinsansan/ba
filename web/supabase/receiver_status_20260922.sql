-- ============================================================
-- 受け子の生存報告 (2026-09-22)
--
-- 経緯: 8/28 のスタンドアロン化以降、受け子は billing.session_state を送らなくなり
--       (LAPLACE_API_KEY を配らないため)、管理画面の稼働ドット・ユーザー画面の「GUI 稼働中」が
--       常に空になっていた。受け子 GUI (BACOPY / KBJAPAN / KBKOREA) が、ログイン中の本人の
--       アクセストークンで 1 分ごとに POST /api/receiver/heartbeat を送り、ここに1行ずつ上書きする。
--       表示専用。ここに書けなくても受け子は止まらない。
-- 1 利用者が複数台・複数の版を使えるよう、(user_id, product, executor_id) で1行。
-- 冪等。
-- ============================================================

create table if not exists public.receiver_status (
  user_id         uuid not null references auth.users(id) on delete cascade,
  product         text not null check (product in ('bacopy', 'kbjapan', 'kbkorea')),
  executor_id     text not null default '',
  email           text,
  last_seen_at    timestamptz not null default now(),
  engine_running  boolean not null default false,
  app_version     text,
  engine_sha      text,
  os              text,
  table_name      text,
  balance         numeric(18,6),
  bets_today      integer,
  wins_today      integer,
  losses_today    integer,
  ties_today      integer,
  bet_errors_today integer,
  last_bet_at     timestamptz,
  payload         jsonb not null default '{}'::jsonb,
  created_at      timestamptz not null default now(),
  primary key (user_id, product, executor_id)
);

create index if not exists idx_receiver_status_last_seen on public.receiver_status(last_seen_at desc);

-- 読み書きはサーバー (service role) だけ。ブラウザからの直接アクセスは許さない。
alter table public.receiver_status enable row level security;

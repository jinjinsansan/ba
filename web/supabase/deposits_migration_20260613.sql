-- deposits: オペレーターが記録する「顧客の入金/ボーナス」。
-- settle cron が残高差分フォールバックで課金する際に当日分を差し引き、
-- 顧客が入金した自分の金に手数料を課さないようにする(2026-06-13)。
-- daily_bet_pnl(ベット記録)で課金できる日は入金を含まないため影響しない。

create table if not exists public.deposits (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles(id) on delete cascade,
  amount      numeric(14,2) not null check (amount > 0),
  date        date not null,                       -- JST の日付 (settle の dateStr と一致させる)
  note        text default '',
  created_at  timestamptz not null default now()
);

create index if not exists deposits_user_date_idx on public.deposits (user_id, date);
create index if not exists deposits_date_idx on public.deposits (date);

-- RLS: service role(admin client / cron)のみ。一般ユーザーからは不可視。
alter table public.deposits enable row level security;

-- 既存ポリシーがあれば作り直し
drop policy if exists deposits_admin_all on public.deposits;
create policy deposits_admin_all on public.deposits
  for all
  to service_role
  using (true)
  with check (true);

comment on table public.deposits is
  'Operator-recorded customer deposits/bonuses. Subtracted by the settle cron balance-diff fallback so deposits are never charged a profit-share fee.';

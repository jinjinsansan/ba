-- 週次課金モデル (2026-06-15)
-- 方針: 会員は基本 is_free。日次自動課金はしないが、日次のベットPnL(純粋・入出金除外)は
-- 全員分を記録 → 土曜締切で月〜土を合算 → 日曜に N%(profit_share_rate) 請求書を発行。
-- キャリー(繰越損)を週単位で計算・可視化する。
-- ※ Supabase SQL Editor に丸ごと貼り付けて Run。idempotent。

-- 1) 日次PnLログ: 全ユーザーの「その日のベット結果PnL」を1日1行(入出金は含まない)。
--    週次ロールアップの元データ。is_free でも記録する。
create table if not exists public.daily_pnl_log (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles(id) on delete cascade,
  date        date not null,                       -- JST の日付
  bet_pnl     numeric(14,2) not null default 0,    -- その日の純粋PnL(daily_bet_pnl 等)
  pnl_source  text,                                -- daily_bet_pnl / master / session_state
  balance     numeric(14,2),                       -- 参考: その時点の残高(検算用)
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (user_id, date)
);
create index if not exists daily_pnl_log_user_date_idx on public.daily_pnl_log (user_id, date);
create index if not exists daily_pnl_log_date_idx on public.daily_pnl_log (date);

alter table public.daily_pnl_log enable row level security;
drop policy if exists daily_pnl_log_admin_all on public.daily_pnl_log;
create policy daily_pnl_log_admin_all on public.daily_pnl_log for all to service_role using (true) with check (true);
drop policy if exists daily_pnl_log_own_select on public.daily_pnl_log;
create policy daily_pnl_log_own_select on public.daily_pnl_log for select using (auth.uid() = user_id);

-- 2) 週次PnL/キャリー履歴: 1ユーザー1週1行。先週・先々週…と履歴で残る。
--    carry_in/net/fee/carry_out を全部保存してキャリー計算を可視化する。
create table if not exists public.weekly_pnl (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles(id) on delete cascade,
  week_start  date not null,                       -- 月曜(JST)
  week_end    date not null,                       -- 土曜(JST・締切)
  gross_pnl   numeric(14,2) not null default 0,    -- 月〜土の純粋PnL合計
  carry_in    numeric(14,2) not null default 0,    -- 週初のキャリー(負債は負の値)
  net_pnl     numeric(14,2) not null default 0,    -- gross_pnl + carry_in
  fee_rate    numeric(6,4)  not null default 0,    -- その時点の profit_share_rate
  fee_amount  numeric(14,2) not null default 0,    -- max(0, net_pnl) * fee_rate
  carry_out   numeric(14,2) not null default 0,    -- min(0, net_pnl) を翌週へ繰越(負債は負)
  invoice_id  uuid references public.invoices(id), -- 発行した請求書(あれば)
  reconcile_delta numeric(14,2),                   -- Σbet_pnl と 残高±入出金 の乖離(検算)
  reconcile_ok    boolean,                         -- 検算が許容内か
  status      text not null default 'billed' check (status in ('billed','no_fee','review')),
  note        text,
  created_at  timestamptz not null default now(),
  unique (user_id, week_start)
);
create index if not exists weekly_pnl_user_week_idx on public.weekly_pnl (user_id, week_start desc);
create index if not exists weekly_pnl_week_idx on public.weekly_pnl (week_start desc);

alter table public.weekly_pnl enable row level security;
drop policy if exists weekly_pnl_admin_all on public.weekly_pnl;
create policy weekly_pnl_admin_all on public.weekly_pnl for all to service_role using (true) with check (true);
drop policy if exists weekly_pnl_own_select on public.weekly_pnl;
create policy weekly_pnl_own_select on public.weekly_pnl for select using (auth.uid() = user_id);

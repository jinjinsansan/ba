-- ============================================================
-- bafather.uk 再構築 (2026-09-13) — 既存 SQL ファイルに無かった分
--
-- 経緯: 8/22 の全停止で旧 Supabase プロジェクトは削除済み。新プロジェクトへ
--       supabase/*.sql を古い順に適用した (ledger_seed.sql と旧投資家の INSERT は除外 = ゼロから開始)。
--       ただし次の2点は SQL ファイルが無かったので、ここで補う。
--   1. daily_profit_invoices … 日次の手数料請求。サイト (cron/settle・payments/credit・me/settlements・admin)
--      と受け子 GUI (未払い判定) が読む。8/22 の控え (daily_profit_invoices.jsonl.gz) の列から再作成。
--   2. billing.product … BACOPY (田辺) / KBJAPAN (梶原) / KBKOREA (韓国) の3版を1つの bafather.uk で管理するため。
-- 冪等。
-- ============================================================

-- ---------- 1. 日次手数料請求 ----------
create table if not exists public.daily_profit_invoices (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users(id) on delete cascade,
  settle_date         date not null,
  daily_profit        numeric(14,2) not null default 0,
  net_profit          numeric(14,2) not null default 0,
  operator_rate       numeric(6,4)  not null default 0,
  operator_fee_amount numeric(14,2) not null default 0,
  referrer_fee_amount numeric(14,2) not null default 0,
  paid_amount         numeric(14,2) not null default 0,
  outstanding_amount  numeric(14,2) not null default 0,
  status              text not null default 'unpaid',
  note                text,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  unique (user_id, settle_date)
);

create index if not exists idx_dpi_status_outstanding
  on public.daily_profit_invoices (status, outstanding_amount);

alter table public.daily_profit_invoices enable row level security;

drop policy if exists dpi_select_own on public.daily_profit_invoices;
create policy dpi_select_own on public.daily_profit_invoices
  for select using (auth.uid() = user_id);

drop policy if exists dpi_admin_all on public.daily_profit_invoices;
create policy dpi_admin_all on public.daily_profit_invoices
  for all using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));

-- ---------- 2. どの版の受け子を使う利用者か ----------
alter table public.billing add column if not exists product text;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'billing_product_check'
  ) then
    alter table public.billing
      add constraint billing_product_check
      check (product is null or product in ('bacopy', 'kbjapan', 'kbkorea'));
  end if;
end $$;

comment on column public.billing.product is
  '受け子アプリの版: bacopy=田辺チーム / kbjapan=梶原チーム / kbkorea=韓国チーム (null=未設定)';

-- ---------- 3. 新規ユーザー作成トリガーの修正 ----------
-- 新しい Supabase プロジェクトでは、auth のトリガーが public を探索パスに持たない状態で実行される。
-- 旧 handle_new_user は search_path 指定なし・profiles を修飾なしで INSERT していたため、
-- 管理者アカウント作成が "Database error creating new user" (500) で失敗した (2026-09-13 実測)。
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $function$
begin
  insert into public.profiles (id, email, referral_code)
  values (
    new.id,
    new.email,
    'REF-' || upper(substr(md5(new.id::text), 1, 8))
  );
  return new;
end;
$function$;

-- ---------- 4. 管理者判定ポリシーの無限再帰を解消 ----------
-- 旧 schema.sql の管理者ポリシーは profiles の中で profiles を参照しており、新プロジェクトでは
-- 'infinite recursion detected in policy for relation "profiles"' (42P17) で全て失敗した。
-- ログイン中の利用者が自分の profiles/billing すら読めず、管理者ページが /me に戻され、
-- 画面遷移のたびにログアウトしたように見えた (2026-09-13 実機)。
-- RLS を通らない security definer の public.is_admin() で判定し、20 個のポリシーを作り直す。

create or replace function public.is_admin(uid uuid default auth.uid())
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce((select is_admin from public.profiles where id = uid), false)
$$;
grant execute on function public.is_admin(uuid) to anon, authenticated;

drop policy if exists "Admins can do anything on billing" on public.billing;
create policy "Admins can do anything on billing" on public.billing as permissive for all to public
  using (public.is_admin());

drop policy if exists "Admins can do anything on charges" on public.charges;
create policy "Admins can do anything on charges" on public.charges as permissive for all to public
  using (public.is_admin());

drop policy if exists "dpi_admin_all" on public.daily_profit_invoices;
create policy "dpi_admin_all" on public.daily_profit_invoices as permissive for all to public
  using (public.is_admin());

drop policy if exists "Admins can do anything on deductions" on public.deductions;
create policy "Admins can do anything on deductions" on public.deductions as permissive for all to public
  using (public.is_admin());

drop policy if exists "Admins can do anything on deliverables" on public.deliverables;
create policy "Admins can do anything on deliverables" on public.deliverables as permissive for all to public
  using (public.is_admin());

drop policy if exists "ledger_acc1_admin_all" on public.ledger_account1_daily;
create policy "ledger_acc1_admin_all" on public.ledger_account1_daily as permissive for all to public
  using (public.is_admin());

drop policy if exists "ledger_acc2_admin_all" on public.ledger_account2_daily;
create policy "ledger_acc2_admin_all" on public.ledger_account2_daily as permissive for all to public
  using (public.is_admin());

drop policy if exists "lab_admin_all" on public.ledger_actual_balances;
create policy "lab_admin_all" on public.ledger_actual_balances as permissive for all to public
  using (public.is_admin());

drop policy if exists "lceb_admin_all" on public.ledger_company_expense_breakdown;
create policy "lceb_admin_all" on public.ledger_company_expense_breakdown as permissive for all to public
  using (public.is_admin());

drop policy if exists "ledger_dist_rules_admin_all" on public.ledger_distribution_rules;
create policy "ledger_dist_rules_admin_all" on public.ledger_distribution_rules as permissive for all to public
  using (public.is_admin());

drop policy if exists "ledger_expense_admin_all" on public.ledger_expense_withdrawals;
create policy "ledger_expense_admin_all" on public.ledger_expense_withdrawals as permissive for all to public
  using (public.is_admin());

drop policy if exists "ledger_investors_admin_all" on public.ledger_investors;
create policy "ledger_investors_admin_all" on public.ledger_investors as permissive for all to public
  using (public.is_admin());

drop policy if exists "ledger_reserve_funds_admin_all" on public.ledger_reserve_funds;
create policy "ledger_reserve_funds_admin_all" on public.ledger_reserve_funds as permissive for all to public
  using (public.is_admin());

drop policy if exists "Admins can do anything on orders" on public.orders;
create policy "Admins can do anything on orders" on public.orders as permissive for all to public
  using (public.is_admin());

drop policy if exists "Admins can update all profiles" on public.profiles;
create policy "Admins can update all profiles" on public.profiles as permissive for update to public
  using (public.is_admin());

drop policy if exists "Admins can view all profiles" on public.profiles;
create policy "Admins can view all profiles" on public.profiles as permissive for select to public
  using (public.is_admin());

drop policy if exists "Admins can do anything on promos" on public.promo_codes;
create policy "Admins can do anything on promos" on public.promo_codes as permissive for all to public
  using (public.is_admin());

drop policy if exists "Admins can do anything on commissions" on public.referral_commissions;
create policy "Admins can do anything on commissions" on public.referral_commissions as permissive for all to public
  using (public.is_admin());

drop policy if exists "Admins can do anything on withdrawals" on public.referral_withdrawals;
create policy "Admins can do anything on withdrawals" on public.referral_withdrawals as permissive for all to public
  using (public.is_admin());

drop policy if exists "Admins can do anything on tickets" on public.support_tickets;
create policy "Admins can do anything on tickets" on public.support_tickets as permissive for all to public
  using (public.is_admin());

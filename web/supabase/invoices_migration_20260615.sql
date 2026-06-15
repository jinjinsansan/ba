-- 管理者発行の請求書 (admin-issued invoices) — 2026-06-15
-- 管理者が任意の金額/メモで請求書を発行 → ユーザーのダッシュボードに表示 →
-- ユーザーがクリックで決済(残高即引き落とし、または不足分は既存の USDT(TRC-20)
-- 自動チャージで入金 → /api/payments/credit が unpaid invoices を自動消し込み)。
create table if not exists public.invoices (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  amount numeric(14,2) not null check (amount > 0),
  memo text,
  status text not null default 'unpaid' check (status in ('unpaid','paid','canceled')),
  created_by uuid references public.profiles(id),
  paid_via text check (paid_via in ('balance','crypto')),
  crypto_payment_id uuid references public.crypto_payments(id),
  created_at timestamptz not null default now(),
  paid_at timestamptz,
  updated_at timestamptz not null default now()
);

create index if not exists invoices_user_status_idx on public.invoices (user_id, status);
create index if not exists invoices_status_idx on public.invoices (status);

alter table public.invoices enable row level security;

-- service_role(サーバAPI) は全操作可。
drop policy if exists invoices_admin_all on public.invoices;
create policy invoices_admin_all on public.invoices for all to service_role using (true) with check (true);

-- 本人は自分の請求書を閲覧可(支払いは API 経由で行うため select のみ)。
drop policy if exists invoices_own_select on public.invoices;
create policy invoices_own_select on public.invoices for select using (auth.uid() = user_id);

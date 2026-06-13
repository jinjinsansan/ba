create table if not exists public.crypto_payments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  kind text not null check (kind in ('license','charge')),
  expected_amount numeric(14,2) not null,
  status text not null default 'pending' check (status in ('pending','credited','expired')),
  tx_hash text unique,
  paid_amount numeric(14,2),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  credited_at timestamptz
);
create index if not exists crypto_payments_status_amount_idx on public.crypto_payments (status, expected_amount);
create index if not exists crypto_payments_user_idx on public.crypto_payments (user_id);
alter table public.crypto_payments enable row level security;
drop policy if exists crypto_payments_admin_all on public.crypto_payments;
create policy crypto_payments_admin_all on public.crypto_payments for all to service_role using (true) with check (true);
drop policy if exists crypto_payments_own_select on public.crypto_payments;
create policy crypto_payments_own_select on public.crypto_payments for select using (auth.uid() = user_id);

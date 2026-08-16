-- ============================================================
-- 招待コードゲート (2026-08-17)
-- 経緯: 8/6 のLP公開化でサインアップが完全オープンになり、8/16 に未知の
--       第三者(dsoldatchenkov2001@gmail.com)が登録→削除済み。
--       以後は「有効な招待コードを持つ人だけ登録できる」状態にする。
-- 2層防御:
--   (1) アプリ層: /signup が /api/auth/invite-check で事前検証(fail-closed)
--   (2) DB層   : auth.users への BEFORE INSERT トリガーで metadata.invite_code を
--                検証 → 無効なら例外。anon key で Supabase Auth API を直叩きしても弾く。
-- 冪等。Supabase SQL Editor に丸ごと貼って実行。
-- ============================================================

create table if not exists public.invite_codes (
  code        text primary key,
  note        text,
  active      boolean not null default true,
  max_uses    integer,                    -- null = 無制限
  uses        integer not null default 0,
  expires_at  timestamptz,                -- null = 無期限
  created_at  timestamptz not null default now(),
  last_used_at timestamptz,
  last_used_email text
);

alter table public.invite_codes enable row level security;
-- ポリシー無し = anon/authenticated からは一切読めない(service_role のみ)

-- ---------- 検証関数(トリガー本体) ----------
create or replace function public.enforce_invite_code()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_code text;
  v_row  public.invite_codes%rowtype;
begin
  v_code := upper(trim(coalesce(new.raw_user_meta_data->>'invite_code', '')));

  if v_code = '' then
    raise exception 'invite code required' using errcode = 'P0001';
  end if;

  select * into v_row from public.invite_codes where code = v_code for update;

  if not found
     or not v_row.active
     or (v_row.expires_at is not null and v_row.expires_at < now())
     or (v_row.max_uses is not null and v_row.uses >= v_row.max_uses) then
    raise exception 'invalid invite code' using errcode = 'P0001';
  end if;

  update public.invite_codes
     set uses = uses + 1,
         last_used_at = now(),
         last_used_email = new.email
   where code = v_code;

  return new;
end;
$$;

drop trigger if exists on_auth_user_invite_check on auth.users;
create trigger on_auth_user_invite_check
  before insert on auth.users
  for each row execute function public.enforce_invite_code();

-- ---------- 初期コード ----------
-- 受け子に配る用。使い回し可(max_uses=null)。運用で増やす/止めるのは
--   insert into invite_codes(code, note) values ('BAF-XXXXXXXX', '誰用');
--   update invite_codes set active=false where code='...';
insert into public.invite_codes (code, note)
values ('BAF-K7Q2M9XW', '初期コード(オーナー配布用) 2026-08-17')
on conflict (code) do nothing;

-- ---------- 確認 ----------
-- select * from public.invite_codes;
-- select tgname, tgenabled from pg_trigger where tgrelid = 'auth.users'::regclass;
--
-- ※ Supabase ダッシュボード「Add user」や admin API createUser で手動追加する場合も
--    このトリガーが効く。その時は user_metadata に {"invite_code":"BAF-..."} を付けるか、
--    一時的に  alter table auth.users disable trigger on_auth_user_invite_check;
--    → 追加 →  alter table auth.users enable trigger on_auth_user_invite_check;

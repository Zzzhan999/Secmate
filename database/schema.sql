-- ============================================================
-- SecMate 数据库 Schema（在 Supabase SQL Editor 中执行）
-- 说明：auth.users 由 Supabase Auth 自动创建，本文件只创建业务表并与其关联。
-- 执行顺序：schema.sql → seed_prompts.sql
-- ============================================================

create extension if not exists "pgcrypto";

-- ========== 1. 用户档案：与 auth.users 1:1 ==========
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text unique,
  plan text not null default 'free' check (plan in ('free', 'pro')),
  created_at timestamptz not null default now()
);

-- 新用户注册时自动创建档案（Supabase 官方推荐模式）
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, username)
  values (new.id, coalesce(new.raw_user_meta_data->>'username', split_part(new.email, '@', 1)))
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ========== 2. 分析记录 ==========
create table if not exists public.analyses (
  id bigserial primary key,
  user_id uuid references public.profiles(id) on delete cascade, -- 可空：匿名分析
  input_type text not null default 'general'
    check (input_type in ('http', 'error', 'code', 'ctf', 'linux', 'protocol', 'general')),
  input_text text not null,
  result_md text,
  model text,
  tokens_in int not null default 0,
  tokens_out int not null default 0,
  created_at timestamptz not null default now()
);
create index if not exists idx_analyses_user_created
  on public.analyses (user_id, created_at desc);

-- ========== 3. 每日配额计数（联合主键保证一人一天一行） ==========
create table if not exists public.daily_usage (
  user_id uuid references public.profiles(id) on delete cascade,
  usage_date date not null default current_date,
  count int not null default 0,
  primary key (user_id, usage_date)
);

-- ========== 4. 订阅 ==========
create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references public.profiles(id) on delete cascade,
  plan text not null check (plan in ('free', 'pro')),
  status text not null default 'active' check (status in ('active', 'canceled', 'expired')),
  started_at timestamptz not null default now(),
  expires_at timestamptz,
  provider text,
  provider_customer_id text
);

-- ========== 5. 订单（支付接口预留，阶段4 接入） ==========
create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  amount_cents int not null,
  currency text not null default 'CNY',
  plan text not null check (plan in ('free', 'pro')),
  status text not null default 'pending' check (status in ('pending', 'paid', 'failed', 'refunded')),
  provider text,
  created_at timestamptz not null default now()
);

-- ========== 6. Prompt 模板（阶段5 后台管理） ==========
create table if not exists public.prompts (
  id serial primary key,
  scene text not null check (scene in ('http', 'error', 'code', 'ctf', 'linux', 'protocol', 'general')),
  name text not null,
  system_prompt text not null,
  version int not null default 1,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

-- ========== 7. 分享链接（阶段5） ==========
create table if not exists public.shared_links (
  id uuid primary key default gen_random_uuid(),
  analysis_id bigint not null unique references public.analyses(id) on delete cascade,
  slug text not null unique,
  is_public boolean not null default true,
  expires_at timestamptz,
  created_at timestamptz not null default now()
);

-- ========== 8. 行级安全：默认拒绝，阶段4 按需放行（服务端走 service_role 不受限） ==========
alter table public.profiles enable row level security;
alter table public.analyses enable row level security;
alter table public.daily_usage enable row level security;
alter table public.subscriptions enable row level security;
alter table public.orders enable row level security;
alter table public.prompts enable row level security;
alter table public.shared_links enable row level security;

-- ========== 9. 配额原子扣减 RPC（阶段4）：未超限则 +1 并返回新计数；超限返回空结果 ==========
create or replace function public.check_and_increment_usage(p_user_id uuid, p_limit int)
returns int
language sql
security definer set search_path = public
as $$
  insert into public.daily_usage (user_id, usage_date, count)
  values (p_user_id, current_date, 1)
  on conflict (user_id, usage_date)
  do update set count = public.daily_usage.count + 1
  where public.daily_usage.count < p_limit
  returning count;
$$;
grant execute on function public.check_and_increment_usage(uuid, int) to service_role;

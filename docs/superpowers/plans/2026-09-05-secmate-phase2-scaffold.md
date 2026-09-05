# SecMate 阶段2（项目结构）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建 SecMate monorepo 脚手架：Next.js 14 前端 + FastAPI 后端 + Supabase schema + 文档，前后端均可直接运行。

**Architecture:** 单仓库四目录（frontend / backend / database / docs）。后端提供 OpenAI 兼容 AI 适配层（覆盖 DeepSeek/OpenAI/Ollama），阶段3 在此骨架上加分析 API；前端用官方脚手架生成后仅做品牌占位（首页为阶段3 交付物）。

**Tech Stack:** Next.js 14.2（App Router + src 目录 + Tailwind + shadcn）、FastAPI + pydantic-settings + httpx、PostgreSQL（Supabase）、pytest。

---

## 文件结构总览

```
SecMate/
├── frontend/                  # Next.js 14 前端（create-next-app 生成 + 品牌占位页）
│   ├── app/layout.tsx         # 根布局：metadata 品牌化
│   ├── app/page.tsx           # 占位首页（阶段3 重写）
│   ├── lib/utils.ts           # shadcn 工具函数
│   ├── components.json        # shadcn 配置
│   └── .env.local.example     # 环境变量模板
├── backend/                   # FastAPI 后端
│   ├── app/
│   │   ├── main.py            # 应用入口：CORS、路由注册、lifespan
│   │   ├── core/config.py     # pydantic-settings 配置
│   │   ├── api/routes/health.py # GET /api/v1/health
│   │   ├── providers/         # AI 适配层（base / openai_compat / factory）
│   │   ├── services/          # 业务逻辑（阶段3 填充）
│   │   ├── schemas/           # Pydantic 模型（阶段3 填充）
│   │   └── prompts/           # Prompt 模板（阶段3 填充）
│   ├── tests/                 # pytest 测试
│   ├── requirements.txt / requirements-dev.txt / pytest.ini
│   ├── Dockerfile / docker-compose.yml / .dockerignore
│   └── .env.example / .gitignore
├── database/
│   ├── schema.sql             # 7 张表 + RLS + 新用户触发器
│   ├── seed_prompts.sql       # 6 场景初始 Prompt
│   └── README.md
├── docs/
│   ├── superpowers/specs/2026-09-05-secmate-design.md   # 设计文档（需求来源）
│   └── superpowers/plans/2026-09-05-secmate-phase2-scaffold.md # 本计划
├── README.md                  # 项目总览与快速开始
├── LICENSE                    # MIT
└── .gitignore                 # 根级忽略规则
```

---

## Task 1: 初始化 git 仓库与根目录文件

**Files:**
- Create: `.gitignore`、`README.md`、`LICENSE`

- [ ] **Step 1: git init**

```bash
cd /d/ku/VScode/Saas && git init -b main
```
Expected: `Initialized empty Git repository`

- [ ] **Step 2: 写根 .gitignore**（node_modules、.next、.venv、__pycache__、.env 系，放行 .env.example）

```gitignore
# 依赖
node_modules/

# 构建产物
.next/
out/
dist/

# Python
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/

# 环境变量（密钥不入库）
.env
.env.*
!.env.example
!.env.local.example

# IDE / OS
.idea/
.vscode/
.DS_Store
Thumbs.db

# 日志
*.log
npm-debug.log*
```

- [ ] **Step 3: 写 README.md**（项目简介、目录结构、快速开始、安全声明）

- [ ] **Step 4: 写 LICENSE**（MIT，Copyright (c) 2026 SecMate）

---

## Task 2: 后端 FastAPI 骨架（TDD）

**Files:**
- Create: `backend/requirements.txt`、`backend/requirements-dev.txt`、`backend/pytest.ini`、`backend/.env.example`、`backend/.gitignore`、`backend/Dockerfile`、`backend/docker-compose.yml`、`backend/.dockerignore`、`backend/app/__init__.py`、`backend/app/main.py`、`backend/app/core/__init__.py`、`backend/app/core/config.py`、`backend/app/api/__init__.py`、`backend/app/api/routes/__init__.py`、`backend/app/api/routes/health.py`、`backend/app/providers/__init__.py`、`backend/app/providers/base.py`、`backend/app/providers/openai_compat.py`、`backend/app/providers/factory.py`、`backend/app/services/__init__.py`、`backend/app/schemas/__init__.py`、`backend/app/prompts/__init__.py`、`backend/tests/test_health.py`、`backend/tests/test_openai_compat_provider.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_health.py`：

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_ok():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "SecMate API"
```

`backend/tests/test_openai_compat_provider.py`：

```python
import json

import httpx
import pytest

from app.providers.base import ProviderError
from app.providers.openai_compat import OpenAICompatProvider


def _sse_handler(request: httpx.Request) -> httpx.Response:
    chunks = [
        {"choices": [{"delta": {"content": "你好"}}]},
        {"choices": [{"delta": {"content": "，"}}]},
        {"choices": [{"delta": {"content": "世界"}}]},
    ]
    body = "".join(f"data: {json.dumps(c, ensure_ascii=False)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    return httpx.Response(200, content=body.encode("utf-8"), headers={"content-type": "text/event-stream"})


def _error_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(401, json={"error": "invalid api key"})


async def test_stream_chat_yields_tokens():
    client = httpx.AsyncClient(transport=httpx.MockTransport(_sse_handler))
    provider = OpenAICompatProvider(
        base_url="https://example.com/v1", api_key="sk-test", model="deepseek-chat", http_client=client
    )
    tokens = [t async for t in provider.stream_chat([{"role": "user", "content": "hi"}])]
    assert "".join(tokens) == "你好，世界"


async def test_stream_chat_raises_provider_error_on_http_error():
    client = httpx.AsyncClient(transport=httpx.MockTransport(_error_handler))
    provider = OpenAICompatProvider(
        base_url="https://example.com/v1", api_key="sk-bad", model="deepseek-chat", http_client=client
    )
    with pytest.raises(ProviderError):
        async for _ in provider.stream_chat([{"role": "user", "content": "hi"}]):
            pass
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m venv .venv && source .venv/Scripts/activate && pip install -r requirements-dev.txt && pytest -q
```
Expected: FAIL（ModuleNotFoundError: app）

- [ ] **Step 3: 写实现**

`backend/app/core/config.py`：

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置：从 backend/.env 读取，环境变量可覆盖（部署时用平台环境变量）。"""

    app_name: str = "SecMate API"
    app_version: str = "0.1.0"
    environment: str = "development"

    # CORS：逗号分隔的多个来源，如 "http://localhost:3000,https://secmate.app"
    cors_origins: list[str] = ["http://localhost:3000"]

    # AI Provider：openai_compat 一套协议覆盖 DeepSeek / OpenAI / Ollama(/v1)
    ai_provider: str = "openai_compat"
    ai_base_url: str = "https://api.deepseek.com/v1"
    ai_api_key: str = ""
    ai_model: str = "deepseek-chat"

    # Supabase（阶段4 用户系统启用；现在可留空，不传则跳过）
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`backend/app/main.py`：

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时打印关键配置（不含密钥），便于排查部署问题
    print(f"[SecMate] {settings.app_name} v{settings.app_version} starting (env={settings.environment})")
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
```

`backend/app/api/routes/health.py`：

```python
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """健康检查：DO 探针与前端联调用。"""
    s = get_settings()
    return {"status": "ok", "app": s.app_name, "version": s.app_version, "environment": s.environment}
```

`backend/app/providers/base.py`：

```python
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class ProviderError(Exception):
    """AI 提供商调用失败（鉴权/网络/限流等）的统一异常，上层据此返回 502。"""


class BaseProvider(ABC):
    """AI 提供商统一抽象：所有实现以流式文本产出，供上层增量渲染。"""

    model: str

    @abstractmethod
    def stream_chat(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """流式对话，逐段产出文本增量。messages 为 OpenAI 格式 [{role, content}]。"""
```

`backend/app/providers/openai_compat.py`：

```python
import json
from collections.abc import AsyncIterator

import httpx

from app.providers.base import BaseProvider, ProviderError


class OpenAICompatProvider(BaseProvider):
    """OpenAI 兼容协议实现：一个实现覆盖 DeepSeek / OpenAI / Ollama(/v1) / vLLM。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._http_client = http_client  # 测试注入 MockTransport 用
        self._timeout = timeout

    async def stream_chat(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        payload = {"model": self.model, "messages": messages, "stream": True}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async def _stream(client: httpx.AsyncClient) -> AsyncIterator[str]:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self._timeout,
                ) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode("utf-8", errors="replace")
                        raise ProviderError(f"AI 提供商返回 {resp.status_code}: {body[:500]}")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue  # 忽略无法解析的心跳行
                        delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                        content = delta.get("content")
                        if content:
                            yield content
            except httpx.HTTPError as exc:
                raise ProviderError(f"AI 提供商连接失败: {exc}") from exc

        if self._http_client is not None:
            async for token in _stream(self._http_client):
                yield token
        else:
            async with httpx.AsyncClient() as client:
                async for token in _stream(client):
                    yield token
```

`backend/app/providers/factory.py`：

```python
from app.core.config import get_settings
from app.providers.base import BaseProvider
from app.providers.openai_compat import OpenAICompatProvider


def get_provider() -> BaseProvider:
    """按配置创建 AI 提供商实例；新增提供商（Claude 等）只需在此注册。"""
    s = get_settings()
    if s.ai_provider == "openai_compat":
        return OpenAICompatProvider(base_url=s.ai_base_url, api_key=s.ai_api_key, model=s.ai_model)
    raise ValueError(f"不支持的 AI_PROVIDER: {s.ai_provider}")
```

`backend/app/providers/__init__.py`：

```python
from app.providers.base import BaseProvider, ProviderError
from app.providers.factory import get_provider

__all__ = ["BaseProvider", "ProviderError", "get_provider"]
```

其余文件：`app/__init__.py` 等空模块；`app/services/__init__.py`、`app/schemas/__init__.py`、`app/prompts/__init__.py` 带一行模块 docstring（阶段3 填充）。

依赖文件：

`backend/requirements.txt`：

```
fastapi>=0.115.0,<1.0.0
uvicorn[standard]>=0.30.0,<1.0.0
pydantic-settings>=2.4.0,<3.0.0
httpx>=0.27.0,<1.0.0
```

`backend/requirements-dev.txt`：

```
-r requirements.txt
pytest>=8.0.0,<9.0.0
pytest-asyncio>=0.23.0,<1.0.0
```

`backend/pytest.ini`：

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

`backend/.env.example`：

```
# 应用
APP_NAME=SecMate API
ENVIRONMENT=development
# CORS（逗号分隔多个来源）
CORS_ORIGINS=http://localhost:3000
# AI Provider（openai_compat 覆盖 DeepSeek/OpenAI/Ollama）
AI_PROVIDER=openai_compat
AI_BASE_URL=https://api.deepseek.com/v1
AI_API_KEY=sk-替换为你的密钥
AI_MODEL=deepseek-chat
# Supabase（阶段4 启用，可留空）
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```

`backend/Dockerfile`：

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`backend/docker-compose.yml`：

```yaml
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
```

`backend/.dockerignore`：

```
.venv
__pycache__
.pytest_cache
.env
tests
```

`backend/.gitignore`：

```
.venv/
__pycache__/
.pytest_cache/
.env
```

- [ ] **Step 4: 运行确认通过**

```bash
pytest -q
```
Expected: `2 passed`

---

## Task 3: 数据库 schema 与种子数据

**Files:**
- Create: `database/schema.sql`、`database/seed_prompts.sql`、`database/README.md`

- [ ] **Step 1: 写 schema.sql**

在 Supabase SQL Editor 执行。内容：

```sql
-- SecMate 数据库 Schema（在 Supabase SQL Editor 中执行）
-- 说明：auth.users 由 Supabase Auth 自动创建，本文件只创建业务表并与其关联。

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

-- ========== 5. 订单（支付接口预留） ==========
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
```

- [ ] **Step 2: 写 seed_prompts.sql**（6 场景共用教育框架 Prompt，七段式输出）

- [ ] **Step 3: 写 database/README.md**（建库步骤、表清单、执行顺序）

---

## Task 4: 前端 Next.js 14 脚手架

**Files:**
- Create（工具生成）: `frontend/` 全套 Next.js 14 脚手架
- Modify: `frontend/app/layout.tsx`（品牌 metadata）、`frontend/app/page.tsx`（占位页）
- Create: `frontend/.env.local.example`

- [ ] **Step 1: 官方脚手架生成**

```bash
cd /d/ku/VScode/Saas && npx --yes create-next-app@14 frontend --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm
```
Expected: 生成完成并自动 `npm install`。

- [ ] **Step 2: shadcn 初始化**

```bash
cd frontend && npx --yes shadcn@latest init -d
```
Expected: 生成 `components.json`、`lib/utils.ts`，改造 `globals.css`。

- [ ] **Step 3: 品牌占位页**

`frontend/app/layout.tsx` metadata 改为 `title: "SecMate"`、`description: "AI Powered Cyber Security Learning Assistant"`。

`frontend/app/page.tsx` 替换为（阶段3 重写为正式首页）：

```tsx
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-950 text-zinc-50">
      <h1 className="text-4xl font-bold tracking-tight">SecMate</h1>
      <p className="text-lg text-zinc-400">AI Powered Cyber Security Learning Assistant</p>
      <p className="text-sm text-zinc-500">脚手架已就绪，阶段3 将实现正式首页与分析页</p>
    </main>
  );
}
```

`frontend/.env.local.example`：

```
# 后端地址（阶段3 起由 /api 代理路由使用）
BACKEND_API_URL=http://localhost:8000
```

- [ ] **Step 4: 验证构建**

```bash
npm run build
```
Expected: 构建成功（TypeScript + ESLint 全通过）。

---

## Task 5: 提交与交付说明

- [ ] **Step 1: 检查 git status**（确认 node_modules/.venv 未入库）

```bash
git status --short | head -50
```

- [ ] **Step 2: 初始提交**

```bash
git add -A && git commit -m "chore: SecMate 阶段2 项目脚手架（前后端 + 数据库 schema + 文档）"
```

- [ ] **Step 3: 输出完整目录树与每个文件作用说明**（阶段2 交付物）

---

## 自审记录

1. **Spec 覆盖**：设计文档第 6-7 节的架构与 7 表 schema 在 Task 2/3 落地；阶段2 范围（目录结构+解释）由 Task 5 Step 3 交付。✓
2. **占位符扫描**：无 TBD/TODO；`services/`、`schemas/`、`prompts/` 明确标注"阶段3 填充"且不实现任何半成品逻辑。✓
3. **类型一致性**：`stream_chat(messages: list[dict[str, str]]) -> AsyncIterator[str]` 在 base/openai_compat/tests 三处一致；`get_settings()` 由 config 定义、main/health/factory 引用一致。✓

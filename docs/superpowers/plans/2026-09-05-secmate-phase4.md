# SecMate 阶段4（商业化）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 SecMate 增加 Supabase Auth 用户系统（邮箱+密码、GitHub OAuth）、Free 5 次/天个人配额（原子扣减）、分析历史列表/详情、定价页（支付预留），匿名分析路径保持阶段3 行为不变。

**Architecture:** 前端 supabase-js 负责注册/登录与 localStorage 会话；所有后端访问走 Next.js 代理透传 `Authorization: Bearer <JWT>`；FastAPI 本地验签（RS256/ES256 走 JWKS 缓存、HS256 走 SUPABASE_JWT_SECRET，零每请求外部调用）；数据访问统一走 PostgREST（httpx + service_role，与现有 recorder.py 一致）；配额用 Postgres RPC 函数单条 SQL 原子扣减；Supabase 未配置/不可用时匿名路径自动降级。

**Tech Stack:** FastAPI + httpx + PyJWT[crypto]；Next.js 14 App Router + @supabase/supabase-js + Tailwind（沿用 shadcn 风格组件与主题 token）；Supabase Auth + PostgREST/PostgreSQL。

**唯一需求来源:** `docs/superpowers/specs/2026-09-05-secmate-phase4-design.md`（已确认）。

---

## 0. 已完成的准备（实施前无需重复）

- 密钥已填入 `backend/.env`（SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY / SUPABASE_JWT_SECRET）与 `frontend/.env.local`（NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY），均不入库。
- `backend/app/core/config.py` 已新增 `supabase_jwt_secret: str = ""` 字段。
- 连接已验证：secret key 走 PostgREST 返回 200（新格式 `sb_secret_*` 可作 apikey）；publishable key 走 GoTrue 返回 200（前端只用它做 Auth，不直连数据库）；JWKS 端点可用。
- **实测发现：本项目 JWT 由单一 ES256（EC P-256）密钥签名**——安全模块必须支持 ES256，同时保留 RS256 与 HS256 路径（设计文档写 RS256，此处以实测为准扩展）。
- `database/schema.sql` 末尾已含配额 RPC 函数 `check_and_increment_usage`（见设计文档 3 节）。

## 0.1 待用户完成的硬前置条件（T10/T18 联调与 E2E 之前必须完成）

1. **执行 schema.sql**：Supabase Dashboard → SQL Editor → New query → 粘贴 `database/schema.sql` 全文 → Run。未执行时 `profiles` 表不存在（已实测 PGRST205）。
2. **关闭邮箱确认**：Dashboard → Authentication → Sign In / Providers → Email → 关闭「Confirm email」。否则注册不会直接返回 session，E2E 无法跑通。

后端单测（T1-T9）不依赖这两项，可先行完成。

## 0.2 全局约定

- 后端测试命令统一为：`cd backend && .venv/Scripts/python.exe -m pytest <path> -v`（Windows Git Bash；pytest 配置见 `backend/pytest.ini`，asyncio_mode=auto，测试内用 `asyncio.run()` 调用异步函数）。
- 提交统一使用（不写入 git config）：
  ```bash
  git add <具体文件>
  git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(backend): 中文描述"
  ```
- 提交粒度：每个任务一个 commit；只 add 本任务涉及的文件。
- 后端测试环境由 `backend/tests/conftest.py`（T1 创建）保证不触碰真实 Supabase。

---

## 文件结构总览

**后端（新增/修改）**
- `backend/requirements.txt` — 改：加 `pyjwt[crypto]`
- `backend/tests/conftest.py` — 新：测试环境隔离（清除 SUPABASE_* 环境变量）
- `backend/app/core/security.py` — 新：JWKS 缓存 + 本地验签（RS256/ES256/HS256）
- `backend/app/api/deps.py` — 新：`get_optional_user` / `require_user` / `UserIdentity`
- `backend/app/services/supabase_rest.py` — 新：PostgREST 通用封装（select / rpc）+ `SupabaseUnavailable`
- `backend/app/services/plans.py` — 新：`PLAN_LIMITS` + `PRICING_PLANS`
- `backend/app/services/usage.py` — 新：`resolve_plan` / `check_and_increment` / `get_usage`
- `backend/app/services/recorder.py` — 改：`record_analysis(..., user_id=None)`
- `backend/app/api/routes/plans.py`、`user.py`、`history.py` — 新：三个 GET 路由
- `backend/app/api/routes/analysis.py` — 改：登录/匿名双分支（见 T9）
- `backend/app/main.py` — 改：注册新路由
- `backend/tests/test_security.py`、`test_deps.py`、`test_supabase_rest.py`、`test_plans.py`、`test_usage.py`、`test_plans_route.py`、`test_user_profile_route.py`、`test_history_route.py` — 新测试
- `backend/tests/test_recorder.py`、`backend/tests/test_analysis_route.py` — 改：补新用例

**前端（新增/修改）**
- `frontend/package.json` — 改：加 `@supabase/supabase-js`
- `frontend/src/lib/supabase.ts` — 新：客户端单例（未配置时为 null）
- `frontend/src/lib/auth.tsx` — 新：AuthProvider + useAuth
- `frontend/src/app/layout.tsx` — 改：挂载 AuthProvider
- `frontend/src/lib/api.ts` — 改：getAuthHeaders/fetchJson/profile/history/plans 封装、streamAnalysis 带 Bearer
- `frontend/src/app/api/analyze/route.ts` — 改：透传 Authorization
- `frontend/src/app/api/[...path]/route.ts` — 新：GET-only 通用代理（plans/user/history 白名单）
- `frontend/src/components/user-menu.tsx`、`quota-badge.tsx`、`upgrade-card.tsx` — 新
- `frontend/src/components/site-header.tsx`、`analyze-client.tsx` — 改
- `frontend/src/app/login/page.tsx`、`pricing/page.tsx`、`history/page.tsx`、`history/[id]/page.tsx` — 新
- `frontend/.env.local.example`、`backend/.env.example` — 改：补新变量样例
- `README.md` — 改：追加阶段4 功能说明
- `e2e/phase4.py` — 新：Playwright E2E 脚本（T18）

---

### Task 1: 后端依赖 pyjwt[crypto] + 测试环境隔离

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: 安装依赖**

Run: `cd backend && .venv/Scripts/python.exe -m pip install "pyjwt[crypto]>=2.9,<3.0"`

Expected: 安装成功（pyjwt 与 cryptography 一并装好）。

- [ ] **Step 2: 更新 requirements.txt**

在 `backend/requirements.txt` 末尾追加一行：

```
pyjwt[crypto]>=2.9,<3.0
```

- [ ] **Step 3: 创建 conftest.py**

新建 `backend/tests/conftest.py`：

```python
import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def hermetic_env(monkeypatch):
    """测试环境隔离：将 Supabase 配置置空，避免本地 .env 已配置时误连真实云端。

    注意必须用 setenv("") 而非 delenv：pydantic-settings 在 os.environ 无该变量时会回退读 .env 文件，
    delenv 挡不住 .env 里的真实凭据（实测会打到真实云端）。
    """
    for var in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        monkeypatch.setenv(var, "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
```

- [ ] **Step 4: 全量回归确认无破坏**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`

Expected: 现有 57 个测试全部通过（conftest 只是把 Supabase 环境变量清空，匿名路径不受影响）。

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/tests/conftest.py
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "chore(backend): 引入 pyjwt[crypto] 并隔离测试环境的 Supabase 配置"
```

---

### Task 2: core/security.py — JWT 本地验签（TDD）

**Files:**
- Create: `backend/tests/test_security.py`
- Create: `backend/app/core/security.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_security.py`：

```python
import asyncio
import base64
import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from app.core.config import get_settings
from app.core.security import JwksError, SupabaseTokenVerifier

ISSUER = "https://xyzcompany.supabase.co/auth/v1"


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _payload(**overrides) -> dict:
    payload = {
        "sub": "user-123",
        "email": "a@b.c",
        "aud": "authenticated",
        "iss": ISSUER,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    payload.update(overrides)
    return payload


def _rsa_jwk(private_key) -> dict:
    pub = private_key.public_key().public_numbers()
    n = pub.n.to_bytes((pub.n.bit_length() + 7) // 8, "big")
    e = pub.e.to_bytes((pub.e.bit_length() + 7) // 8, "big")
    return {"kty": "RSA", "alg": "RS256", "use": "sig", "kid": "rsa-kid", "n": _b64u(n), "e": _b64u(e)}


def _ec_jwk(private_key) -> dict:
    pub = private_key.public_key().public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "alg": "ES256",
        "use": "sig",
        "kid": "ec-kid",
        "x": _b64u(pub.x.to_bytes(32, "big")),
        "y": _b64u(pub.y.to_bytes(32, "big")),
    }


def _verifier_with_jwks(monkeypatch, responses: list[list[dict]]):
    """构造带 MockTransport 的验签器；responses 按请求次数依次返回 JWKS。"""
    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    get_settings.cache_clear()
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        idx = min(calls["count"], len(responses) - 1)
        calls["count"] += 1
        return httpx.Response(200, json={"keys": responses[idx]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return SupabaseTokenVerifier(http_client=client), calls


@pytest.fixture
def configured_hs256(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_hs256_valid_token_passes(configured_hs256):
    token = jwt.encode(_payload(), "test-secret", algorithm="HS256")
    payload = asyncio.run(SupabaseTokenVerifier().verify(token))
    assert payload["sub"] == "user-123"
    assert payload["email"] == "a@b.c"


def test_hs256_wrong_secret_rejected(configured_hs256):
    token = jwt.encode(_payload(), "other-secret", algorithm="HS256")
    with pytest.raises(jwt.PyJWTError):
        asyncio.run(SupabaseTokenVerifier().verify(token))


def test_hs256_expired_rejected(configured_hs256):
    token = jwt.encode(_payload(exp=int(time.time()) - 60), "test-secret", algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        asyncio.run(SupabaseTokenVerifier().verify(token))


def test_hs256_wrong_audience_rejected(configured_hs256):
    token = jwt.encode(_payload(aud="wrong"), "test-secret", algorithm="HS256")
    with pytest.raises(jwt.InvalidAudienceError):
        asyncio.run(SupabaseTokenVerifier().verify(token))


def test_hs256_wrong_issuer_rejected(configured_hs256):
    token = jwt.encode(_payload(iss="https://evil.example.com/auth/v1"), "test-secret", algorithm="HS256")
    with pytest.raises(jwt.InvalidIssuerError):
        asyncio.run(SupabaseTokenVerifier().verify(token))


def test_hs256_missing_exp_rejected(configured_hs256):
    payload = _payload()
    payload.pop("exp")
    token = jwt.encode(payload, "test-secret", algorithm="HS256")
    with pytest.raises(jwt.MissingRequiredClaimError):
        asyncio.run(SupabaseTokenVerifier().verify(token))


def test_rs256_via_mock_jwks_passes(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier, _ = _verifier_with_jwks(monkeypatch, [[_rsa_jwk(key)]])
    token = jwt.encode(_payload(), key, algorithm="RS256", headers={"kid": "rsa-kid"})
    payload = asyncio.run(verifier.verify(token))
    assert payload["sub"] == "user-123"


def test_es256_via_mock_jwks_passes(monkeypatch):
    # 实测本项目 Supabase 用 ES256 签发 JWT，此路径必须支持
    key = ec.generate_private_key(ec.SECP256R1())
    verifier, _ = _verifier_with_jwks(monkeypatch, [[_ec_jwk(key)]])
    token = jwt.encode(_payload(), key, algorithm="ES256", headers={"kid": "ec-kid"})
    payload = asyncio.run(verifier.verify(token))
    assert payload["sub"] == "user-123"


def test_jwks_cached_within_ttl(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier, calls = _verifier_with_jwks(monkeypatch, [[_rsa_jwk(key)]])
    token = jwt.encode(_payload(), key, algorithm="RS256", headers={"kid": "rsa-kid"})
    asyncio.run(verifier.verify(token))
    asyncio.run(verifier.verify(token))
    assert calls["count"] == 1  # 缓存命中，不重复拉取


def test_jwks_kid_miss_triggers_refresh(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier, calls = _verifier_with_jwks(monkeypatch, [[], [_rsa_jwk(key)]])
    token = jwt.encode(_payload(), key, algorithm="RS256", headers={"kid": "rsa-kid"})
    payload = asyncio.run(verifier.verify(token))
    assert payload["sub"] == "user-123"
    assert calls["count"] == 2  # 首次未命中后自动刷新一次


def test_jwks_fetch_http_error_raises_jwks_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    get_settings.cache_clear()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    verifier = SupabaseTokenVerifier(http_client=client)
    token = "x.y.z"  # 触发 JWKS 拉取前的 header 解析会先失败，改用 RS256 头
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(_payload(), key, algorithm="RS256", headers={"kid": "rsa-kid"})
    with pytest.raises(JwksError):
        asyncio.run(verifier.verify(token))


def test_unconfigured_supabase_raises_jwks_error():
    # conftest 已清除 SUPABASE_*，直接验 RS256 token 应在拉取 JWKS 时失败
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(_payload(), key, algorithm="RS256", headers={"kid": "rsa-kid"})
    with pytest.raises(JwksError):
        asyncio.run(SupabaseTokenVerifier().verify(token))


def test_hs256_without_secret_raises_jwks_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    get_settings.cache_clear()
    token = jwt.encode(_payload(), "whatever", algorithm="HS256")
    with pytest.raises(JwksError):
        asyncio.run(SupabaseTokenVerifier().verify(token))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_security.py -q`

Expected: 收集失败（`ModuleNotFoundError: app.core.security`）。

- [ ] **Step 3: 实现 security.py**

新建 `backend/app/core/security.py`：

```python
import time

import httpx
import jwt

from app.core.config import get_settings


class JwksError(Exception):
    """JWKS 拉取失败或验签依赖不可用（上层转 503）。"""


class SupabaseTokenVerifier:
    """Supabase JWT 本地验签。

    RS256/ES256：JWKS 缓存（TTL 24h），kid 未命中自动刷新一次（应对密钥轮换）。
    HS256：SUPABASE_JWT_SECRET。
    校验 aud=authenticated、iss={SUPABASE_URL}/auth/v1、exp/sub 必填。
    """

    JWKS_PATH = "/auth/v1/.well-known/jwks.json"
    TTL_SECONDS = 24 * 3600

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self._http_client = http_client
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float = 0.0

    async def _get(self, url: str) -> httpx.Response:
        if self._http_client is not None:
            return await self._http_client.get(url)
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await client.get(url)

    async def _fetch_jwks(self) -> dict[str, jwt.PyJWK]:
        s = get_settings()
        if not s.supabase_url:
            raise JwksError("Supabase 未配置")
        url = f"{s.supabase_url.rstrip('/')}{self.JWKS_PATH}"
        try:
            resp = await self._get(url)
        except httpx.HTTPError as exc:
            raise JwksError(f"JWKS 拉取失败: {exc}") from exc
        if resp.status_code >= 400:
            raise JwksError(f"JWKS 拉取失败: HTTP {resp.status_code}")
        try:
            keys = resp.json()["keys"]
        except (ValueError, KeyError) as exc:
            raise JwksError("JWKS 响应格式异常") from exc
        return {k["kid"]: jwt.PyJWK(k) for k in keys if k.get("kid")}

    async def _key_for(self, kid: str):
        if not self._keys or time.monotonic() - self._fetched_at > self.TTL_SECONDS:
            self._keys = await self._fetch_jwks()
            self._fetched_at = time.monotonic()
        if kid not in self._keys:
            # 密钥可能已轮换：刷新一次缓存再试
            self._keys = await self._fetch_jwks()
            self._fetched_at = time.monotonic()
        if kid not in self._keys:
            raise JwksError(f"JWKS 中不存在 kid={kid}")
        return self._keys[kid].key

    async def verify(self, token: str) -> dict:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        s = get_settings()
        if alg == "HS256":
            if not s.supabase_jwt_secret:
                raise JwksError("未配置 SUPABASE_JWT_SECRET")
            key = s.supabase_jwt_secret
        elif alg in ("RS256", "ES256"):
            kid = header.get("kid")
            if not kid:
                raise jwt.InvalidKeyError("JWT 头缺少 kid")
            key = await self._key_for(kid)
        else:
            raise jwt.InvalidAlgorithmError(f"不支持的签名算法: {alg}")
        return jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience="authenticated",
            issuer=f"{s.supabase_url.rstrip('/')}/auth/v1",
            options={"require": ["exp", "sub"]},
        )


_verifier: SupabaseTokenVerifier | None = None


def get_verifier() -> SupabaseTokenVerifier:
    global _verifier
    if _verifier is None:
        _verifier = SupabaseTokenVerifier()
    return _verifier


def reset_verifier() -> None:
    global _verifier
    _verifier = None


async def verify_supabase_token(token: str) -> dict:
    """模块级入口：验签成功返回 payload（含 sub/email/role/exp 等声明）。"""
    return await get_verifier().verify(token)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_security.py -q`

Expected: 15 passed。

- [ ] **Step 5: 全量回归**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`

Expected: 全部通过（73 个）。

> **实施记录（代码质量审查驱动的修订，commit 5f85357）：** 计划原版代码有两处安全缺陷，已按审查结论修订：
> 1. `_key_for` 改为返回 `jwt.PyJWK` 对象而非裸 key——alg 与密钥类型不匹配时抛 `InvalidAlgorithmError`（PyJWTError→401），避免裸 TypeError 穿透成 500。
> 2. 未知 kid 不再无条件刷新 JWKS：新增 `REFRESH_MIN_INTERVAL=60s` 最小刷新间隔防拉取放大；缓存新鲜时未知 kid 直接抛 `jwt.InvalidKeyError`（401 语义）。
> 3. `_fetch_jwks` 将 `jwt.PyJWK(k)` 构造异常包装为 `JwksError`。
> 测试相应增补 `test_jwks_kid_miss_within_interval_does_not_refetch` 与 `test_alg_key_type_mismatch_rejected`，共 15 个。

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(backend): Supabase JWT 本地验签（JWKS 缓存，支持 RS256/ES256/HS256）"
```

---

### Task 3: api/deps.py — 身份依赖（TDD）

**Files:**
- Create: `backend/tests/test_deps.py`
- Create: `backend/app/api/deps.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_deps.py`：

```python
import asyncio
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from starlette.requests import Request

from app.api.deps import get_optional_user, require_user
from app.core.config import get_settings

ISSUER = "https://xyzcompany.supabase.co/auth/v1"


def _payload() -> dict:
    return {
        "sub": "user-123",
        "email": "a@b.c",
        "aud": "authenticated",
        "iss": ISSUER,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }


def make_request(auth: str | None) -> Request:
    headers = [(b"host", b"test")]
    if auth:
        headers.append((b"authorization", auth.encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def test_no_token_returns_none():
    user = asyncio.run(get_optional_user(make_request(None)))
    assert user is None


def test_valid_hs256_token_returns_identity(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")
    get_settings.cache_clear()
    token = jwt.encode(_payload(), "test-secret", algorithm="HS256")
    user = asyncio.run(get_optional_user(make_request(f"Bearer {token}")))
    assert user is not None
    assert user.id == "user-123"
    assert user.email == "a@b.c"


def test_malformed_token_returns_401():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_optional_user(make_request("Bearer not-a-jwt")))
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "invalid_token"


def test_tampered_token_returns_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")
    get_settings.cache_clear()
    token = jwt.encode(_payload(), "test-secret", algorithm="HS256")
    tampered = token[:-2] + ("ab" if not token.endswith("ab") else "cd")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_optional_user(make_request(f"Bearer {tampered}")))
    assert exc.value.status_code == 401


def test_require_user_without_token_401():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_user(make_request(None)))
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "unauthorized"


def test_require_user_with_valid_token(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")
    get_settings.cache_clear()
    token = jwt.encode(_payload(), "test-secret", algorithm="HS256")
    user = asyncio.run(require_user(make_request(f"Bearer {token}")))
    assert user.id == "user-123"


def test_token_when_supabase_unconfigured_503():
    # conftest 已清空 Supabase 配置：带 RS256 token 无法拉取 JWKS → 503
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(_payload(), key, algorithm="RS256", headers={"kid": "k"})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_optional_user(make_request(f"Bearer {token}")))
    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "supabase_unavailable"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_deps.py -q`

Expected: 收集失败（`ModuleNotFoundError: app.api.deps`）。

- [ ] **Step 3: 实现 deps.py**

新建 `backend/app/api/deps.py`：

```python
from dataclasses import dataclass

import jwt
from fastapi import HTTPException, Request

from app.core.security import JwksError, verify_supabase_token


@dataclass(frozen=True)
class UserIdentity:
    """验签通过后的最小用户身份。id 即 Supabase auth.users 的 UUID（JWT sub）。"""

    id: str
    email: str | None = None
    role: str | None = None


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    return token or None


async def get_optional_user(request: Request) -> UserIdentity | None:
    """无 token 返回 None（匿名路径）；token 无效 401；验签依赖不可用 503。"""
    token = _bearer_token(request)
    if token is None:
        return None
    try:
        payload = await verify_supabase_token(token)
    except JwksError:
        raise HTTPException(
            status_code=503,
            detail={"code": "supabase_unavailable", "message": "认证服务暂时不可用，请稍后重试。"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_token", "message": "登录状态无效或已过期，请重新登录。"},
        )
    return UserIdentity(
        id=str(payload["sub"]),
        email=payload.get("email"),
        role=payload.get("role"),
    )


async def require_user(request: Request) -> UserIdentity:
    user = await get_optional_user(request)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "请先登录。"},
        )
    return user
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_deps.py -q`

Expected: 7 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/deps.py backend/tests/test_deps.py
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(backend): 身份依赖 get_optional_user/require_user（401/503 错误矩阵）"
```

---

### Task 4: services/supabase_rest.py — PostgREST 封装（TDD）

**Files:**
- Create: `backend/tests/test_supabase_rest.py`
- Create: `backend/app/services/supabase_rest.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_supabase_rest.py`：

```python
import asyncio
import json

import httpx
import pytest

from app.core.config import get_settings
from app.services.supabase_rest import SupabaseUnavailable, rpc, select


def test_unconfigured_raises_unavailable():
    with pytest.raises(SupabaseUnavailable):
        asyncio.run(select("profiles"))


def test_rpc_sends_service_role_headers(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=6)

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(
        rpc("check_and_increment_usage", {"p_user_id": "u1", "p_limit": 5}, http_client=client)
    )
    assert result == 6
    assert captured["url"].endswith("/rest/v1/rpc/check_and_increment_usage")
    assert captured["headers"]["apikey"] == "svc-key"
    assert captured["headers"]["authorization"] == "Bearer svc-key"
    assert captured["body"] == {"p_user_id": "u1", "p_limit": 5}


def test_rpc_empty_body_returns_empty_list(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(
        rpc("check_and_increment_usage", {"p_user_id": "u1", "p_limit": 5}, http_client=client)
    )
    assert result == []


def test_select_builds_query_params(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=[{"plan": "free"}])

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    rows = asyncio.run(
        select(
            "profiles",
            select_fields="plan",
            params={"id": "eq.u1"},
            http_client=client,
        )
    )
    assert rows == [{"plan": "free"}]
    assert captured["url"].startswith("https://xyzcompany.supabase.co/rest/v1/profiles")
    assert "select=plan" in captured["url"]
    assert "id=eq.u1" in captured["url"]


def test_http_error_raises_unavailable(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(SupabaseUnavailable):
        asyncio.run(select("profiles", http_client=client))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_supabase_rest.py -q`

Expected: 收集失败（`ModuleNotFoundError: app.services.supabase_rest`）。

- [ ] **Step 3: 实现 supabase_rest.py**

新建 `backend/app/services/supabase_rest.py`：

```python
import httpx

from app.core.config import get_settings

_REST_PATH = "/rest/v1"


class SupabaseUnavailable(Exception):
    """Supabase 未配置或请求失败。认证/配额/历史路径的上层转 503。"""


def _headers() -> dict[str, str]:
    s = get_settings()
    return {
        "apikey": s.supabase_service_role_key,
        "Authorization": f"Bearer {s.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


async def _request(
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    json_body: dict | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> httpx.Response:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        raise SupabaseUnavailable("Supabase 未配置")
    url = f"{s.supabase_url.rstrip('/')}{_REST_PATH}{path}"

    async def _call(client: httpx.AsyncClient) -> httpx.Response:
        try:
            return await client.request(method, url, params=params, json=json_body, headers=_headers())
        except httpx.HTTPError as exc:
            raise SupabaseUnavailable(f"Supabase 请求失败: {exc}") from exc

    if http_client is not None:
        resp = await _call(http_client)
    else:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await _call(client)
    if resp.status_code >= 400:
        raise SupabaseUnavailable(f"Supabase 返回 {resp.status_code}")
    return resp


async def select(
    table: str,
    *,
    select_fields: str = "*",
    params: dict[str, str] | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """GET /rest/v1/{table}?select=... 返回行数组（service_role 绕过 RLS）。"""
    all_params = {"select": select_fields, **(params or {})}
    resp = await _request("GET", f"/{table}", params=all_params, http_client=http_client)
    return resp.json()


async def rpc(
    fn_name: str,
    args: dict,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list | int | None:
    """POST /rest/v1/rpc/{fn}。标量函数返回标量，集合函数返回数组，无行返回 []。"""
    resp = await _request("POST", f"/rpc/{fn_name}", json_body=args, http_client=http_client)
    if not resp.content:
        return []
    return resp.json()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_supabase_rest.py -q`

Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/supabase_rest.py backend/tests/test_supabase_rest.py
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(backend): PostgREST 通用封装 select/rpc（service_role + 可注入客户端）"
```

---

### Task 5: services/plans.py — 配额与定价配置（TDD）

**Files:**
- Create: `backend/tests/test_plans.py`
- Create: `backend/app/services/plans.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_plans.py`：

```python
from app.services.plans import PLAN_LIMITS, PRICING_PLANS


def test_plan_limits():
    assert PLAN_LIMITS == {"free": 5, "pro": 200}


def test_pricing_has_four_plans():
    assert len(PRICING_PLANS) == 4
    ids = [p["id"] for p in PRICING_PLANS]
    assert ids == ["free", "pro_monthly", "pro_yearly", "pro_student"]


def test_only_pro_plans_marked_coming_soon():
    free = next(p for p in PRICING_PLANS if p["id"] == "free")
    assert free["coming_soon"] is False
    assert free["cta_text"] == "当前方案"
    for p in PRICING_PLANS:
        if p["id"] != "free":
            assert p["coming_soon"] is True
            assert p["cta_text"] == "即将上线"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_plans.py -q`

Expected: 收集失败（`ModuleNotFoundError: app.services.plans`）。

- [ ] **Step 3: 实现 plans.py**

新建 `backend/app/services/plans.py`：

```python
"""套餐配置：配额上限与定价页数据（/api/v1/plans 单一数据源）。"""

PLAN_LIMITS = {"free": 5, "pro": 200}

PRICING_PLANS = [
    {
        "id": "free",
        "name": "Free",
        "price": 0,
        "price_unit": "永久免费",
        "description": "入门学习，无需注册",
        "features": ["每日 5 次完整分析", "六类输入自动识别", "流式 Markdown + 代码高亮", "匿名使用"],
        "highlighted": False,
        "cta_text": "当前方案",
        "coming_soon": False,
    },
    {
        "id": "pro_monthly",
        "name": "Pro 月付",
        "price": 19,
        "price_unit": "元/月",
        "description": "备考冲刺、高频练习",
        "features": ["每日 200 次分析上限", "完整分析历史记录", "更强模型优先队列", "学习笔记整理（阶段5）"],
        "highlighted": True,
        "cta_text": "即将上线",
        "coming_soon": True,
    },
    {
        "id": "pro_yearly",
        "name": "Pro 年付",
        "price": 168,
        "price_unit": "元/年（省 60 元）",
        "description": "长期学习最划算",
        "features": ["含 Pro 月付全部权益", "年付优惠价", "3 天免费试用（后续开放）"],
        "highlighted": False,
        "cta_text": "即将上线",
        "coming_soon": True,
    },
    {
        "id": "pro_student",
        "name": "学生 Pro",
        "price": 9.9,
        "price_unit": "元/月",
        "description": "在校学生专属",
        "features": ["含 Pro 月付全部权益", "edu 邮箱验证（后续开放）"],
        "highlighted": False,
        "cta_text": "即将上线",
        "coming_soon": True,
    },
]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_plans.py -q`

Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/plans.py backend/tests/test_plans.py
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(backend): 套餐配置（Free/Pro 限额与四档定价数据）"
```

---

### Task 6: services/usage.py — 套餐解析与配额扣减（TDD）

**Files:**
- Create: `backend/tests/test_usage.py`
- Create: `backend/app/services/usage.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_usage.py`：

```python
import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.core.config import get_settings
from app.services.usage import check_and_increment, get_usage, resolve_plan

NOW = datetime.now(timezone.utc)


def _client(monkeypatch, routes: dict[str, list | int]):
    """routes: profiles/subscriptions/daily_usage/rpc 各自返回的 JSON 或 "empty"（空响应体）。"""
    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/rpc/" in url:
            body = routes.get("rpc")
            if body == "empty":
                return httpx.Response(200, content=b"")
            return httpx.Response(200, json=body)
        if "profiles" in url:
            return httpx.Response(200, json=routes.get("profiles", []))
        if "subscriptions" in url:
            return httpx.Response(200, json=routes.get("subscriptions", []))
        if "daily_usage" in url:
            return httpx.Response(200, json=routes.get("daily_usage", []))
        return httpx.Response(404, json={})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_resolve_plan_free_fast_path(monkeypatch):
    client = _client(monkeypatch, {"profiles": [{"plan": "free"}]})
    plan = asyncio.run(resolve_plan("u1", http_client=client))
    assert plan == "free"


def test_resolve_plan_missing_profile_defaults_free(monkeypatch):
    client = _client(monkeypatch, {"profiles": []})
    plan = asyncio.run(resolve_plan("u1", http_client=client))
    assert plan == "free"


def test_resolve_plan_pro_with_active_unexpired_sub(monkeypatch):
    future = (NOW + timedelta(days=30)).isoformat()
    client = _client(
        monkeypatch,
        {"profiles": [{"plan": "pro"}], "subscriptions": [{"status": "active", "expires_at": future}]},
    )
    plan = asyncio.run(resolve_plan("u1", http_client=client))
    assert plan == "pro"


def test_resolve_plan_pro_with_no_expiry_stays_pro(monkeypatch):
    client = _client(
        monkeypatch,
        {"profiles": [{"plan": "pro"}], "subscriptions": [{"status": "active", "expires_at": None}]},
    )
    plan = asyncio.run(resolve_plan("u1", http_client=client))
    assert plan == "pro"


def test_resolve_plan_pro_with_expired_sub_falls_back_free(monkeypatch):
    past = (NOW - timedelta(days=1)).isoformat()
    client = _client(
        monkeypatch,
        {"profiles": [{"plan": "pro"}], "subscriptions": [{"status": "active", "expires_at": past}]},
    )
    plan = asyncio.run(resolve_plan("u1", http_client=client))
    assert plan == "free"


def test_resolve_plan_pro_without_sub_falls_back_free(monkeypatch):
    client = _client(monkeypatch, {"profiles": [{"plan": "pro"}], "subscriptions": []})
    plan = asyncio.run(resolve_plan("u1", http_client=client))
    assert plan == "free"


def test_check_and_increment_success(monkeypatch):
    client = _client(monkeypatch, {"rpc": 6})
    ok = asyncio.run(check_and_increment("u1", 5, http_client=client))
    assert ok is True


def test_check_and_increment_quota_exceeded(monkeypatch):
    client = _client(monkeypatch, {"rpc": "empty"})
    ok = asyncio.run(check_and_increment("u1", 5, http_client=client))
    assert ok is False


def test_get_usage_returns_count(monkeypatch):
    client = _client(monkeypatch, {"daily_usage": [{"count": 3}]})
    used = asyncio.run(get_usage("u1", http_client=client))
    assert used == 3


def test_get_usage_zero_when_no_row(monkeypatch):
    client = _client(monkeypatch, {"daily_usage": []})
    used = asyncio.run(get_usage("u1", http_client=client))
    assert used == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_usage.py -q`

Expected: 收集失败（`ModuleNotFoundError: app.services.usage`）。

- [ ] **Step 3: 实现 usage.py**

新建 `backend/app/services/usage.py`：

```python
"""个人配额：套餐解析（profiles.plan + subscriptions 校验）与 RPC 原子扣减。"""

from datetime import datetime, timezone

from app.services.supabase_rest import rpc, select


async def resolve_plan(user_id: str, http_client=None) -> str:
    """profiles.plan 快速路径；plan=pro 时需存在有效订阅（active 且未过期），否则按 free 计。"""
    rows = await select(
        "profiles",
        select_fields="plan",
        params={"id": f"eq.{user_id}"},
        http_client=http_client,
    )
    plan = rows[0].get("plan", "free") if rows else "free"
    if plan != "pro":
        return plan
    subs = await select(
        "subscriptions",
        select_fields="status,expires_at",
        params={"user_id": f"eq.{user_id}", "status": "eq.active"},
        http_client=http_client,
    )
    now = datetime.now(timezone.utc)
    for sub in subs:
        expires_at = sub.get("expires_at")
        if not expires_at:
            return "pro"  # 无过期时间视为永久有效
        try:
            if datetime.fromisoformat(expires_at.replace("Z", "+00:00")) > now:
                return "pro"
        except ValueError:
            continue
    return "free"


async def check_and_increment(user_id: str, limit: int, http_client=None) -> bool:
    """RPC 原子扣减：未超限返回 True，超限（空结果）返回 False。"""
    result = await rpc(
        "check_and_increment_usage",
        {"p_user_id": user_id, "p_limit": limit},
        http_client=http_client,
    )
    return bool(result)


async def get_usage(user_id: str, http_client=None) -> int:
    """今日已用次数；无记录为 0。usage_date 以 UTC 对齐（Supabase 服务器时区）。"""
    today = datetime.now(timezone.utc).date().isoformat()
    rows = await select(
        "daily_usage",
        select_fields="count",
        params={"user_id": f"eq.{user_id}", "usage_date": f"eq.{today}"},
        http_client=http_client,
    )
    return int(rows[0]["count"]) if rows else 0
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_usage.py -q`

Expected: 10 passed。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/usage.py backend/tests/test_usage.py
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(backend): 配额服务——套餐解析与 RPC 原子扣减"
```

---

### Task 7: recorder.py 支持登录用户落库（TDD）

**Files:**
- Modify: `backend/app/services/recorder.py`
- Modify: `backend/tests/test_recorder.py`

- [ ] **Step 1: 补失败测试**

在 `backend/tests/test_recorder.py` 末尾追加：

```python
def test_posts_user_id_when_logged_in(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{"id": 99}])

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key-123")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(record_analysis(
        input_type="general", input_text="hi", result_md="ok",
        model="deepseek-chat", tokens_in=1, tokens_out=1,
        user_id="user-123", http_client=client,
    ))
    assert result == 99
    assert captured["body"]["user_id"] == "user-123"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_recorder.py::test_posts_user_id_when_logged_in -q`

Expected: FAIL（`TypeError: record_analysis() got an unexpected keyword argument 'user_id'`）。

- [ ] **Step 3: 修改 recorder.py**

修改 `backend/app/services/recorder.py`：

```python
import httpx

from app.core.config import get_settings

_INSERT_PATH = "/rest/v1/analyses"


async def record_analysis(
    *,
    input_type: str,
    input_text: str,
    result_md: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    user_id: str | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> int | None:
    """分析落库（PostgREST + service_role，可绕过 RLS）。user_id 为空=匿名分析。
    未配置 Supabase 时跳过，保证本地可无库运行。"""
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        print("[SecMate] Supabase 未配置，跳过分析落库")
        return None

    payload = {
        "user_id": user_id,
        "input_type": input_type,
        "input_text": input_text,
        "result_md": result_md,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }
    headers = {
        "apikey": s.supabase_service_role_key,
        "Authorization": f"Bearer {s.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    async def _post(client: httpx.AsyncClient) -> int | None:
        try:
            resp = await client.post(
                f"{s.supabase_url.rstrip('/')}{_INSERT_PATH}",
                json=payload,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            print(f"[SecMate] 落库失败（网络）: {exc}")
            return None
        if resp.status_code >= 400:
            print(f"[SecMate] 落库失败: {resp.status_code} {resp.text[:300]}")
            return None
        try:
            rows = resp.json()
            return int(rows[0]["id"]) if rows else None
        except (ValueError, KeyError, IndexError):
            return None

    if http_client is not None:
        return await _post(http_client)
    async with httpx.AsyncClient(timeout=10.0) as client:
        return await _post(client)
```

（改动点：签名加 `user_id: str | None = None`，payload 中 `"user_id": None` → `"user_id": user_id`。）

- [ ] **Step 4: 运行全部 recorder 测试**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_recorder.py -q`

Expected: 4 passed（原 3 个 + 新 1 个）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/recorder.py backend/tests/test_recorder.py
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(backend): 分析落库支持登录用户 user_id"
```

---

### Task 8: 新增 plans/user/history 路由并注册（TDD）

**Files:**
- Create: `backend/app/api/routes/plans.py`
- Create: `backend/app/api/routes/user.py`
- Create: `backend/app/api/routes/history.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_plans_route.py`
- Create: `backend/tests/test_user_profile_route.py`
- Create: `backend/tests/test_history_route.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_plans_route.py`：

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_plans_returns_four_plans():
    resp = client.get("/api/v1/plans")
    assert resp.status_code == 200
    plans = resp.json()["plans"]
    assert len(plans) == 4
    assert plans[0]["id"] == "free"
    assert any(p["coming_soon"] for p in plans)
```

新建 `backend/tests/test_user_profile_route.py`：

```python
import pytest
from fastapi.testclient import TestClient

import app.api.routes.user as user_module
from app.api.deps import UserIdentity, require_user
from app.main import app
from app.services.supabase_rest import SupabaseUnavailable

client = TestClient(app)


@pytest.fixture
def logged_in():
    app.dependency_overrides[require_user] = lambda: UserIdentity(id="u1", email="a@b.c")
    yield
    app.dependency_overrides.clear()


def test_profile_shape(logged_in, monkeypatch):
    async def fake_resolve(user_id):
        return "free"

    async def fake_usage(user_id):
        return 3

    monkeypatch.setattr(user_module, "resolve_plan", fake_resolve)
    monkeypatch.setattr(user_module, "get_usage", fake_usage)

    resp = client.get("/api/v1/user/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"email": "a@b.c", "plan": "free", "used_today": 3, "limit": 5, "remaining": 2}


def test_profile_supabase_down_returns_503(logged_in, monkeypatch):
    async def boom(user_id):
        raise SupabaseUnavailable("down")

    monkeypatch.setattr(user_module, "resolve_plan", boom)

    resp = client.get("/api/v1/user/profile")
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "supabase_unavailable"


def test_profile_requires_login():
    resp = client.get("/api/v1/user/profile")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "unauthorized"
```

新建 `backend/tests/test_history_route.py`：

```python
import pytest
from fastapi.testclient import TestClient

import app.api.routes.history as history_module
from app.api.deps import UserIdentity, require_user
from app.main import app
from app.services.supabase_rest import SupabaseUnavailable

client = TestClient(app)

ROW = {
    "id": 1,
    "input_type": "ctf",
    "input_text": "flag{" + "x" * 200 + "}",
    "result_md": "## 分析\n内容",
    "model": "glm-4-flash",
    "tokens_in": 30,
    "tokens_out": 100,
    "created_at": "2026-09-05T10:00:00+00:00",
}


@pytest.fixture
def logged_in():
    app.dependency_overrides[require_user] = lambda: UserIdentity(id="u1", email="a@b.c")
    yield
    app.dependency_overrides.clear()


def test_list_history_with_has_more(logged_in, monkeypatch):
    captured: dict = {}

    async def fake_select(table, *, select_fields="*", params=None, http_client=None):
        captured["table"] = table
        captured["params"] = params
        return [dict(ROW, id=i) for i in range(1, 12)]  # 多取 1 条 → has_more=True

    monkeypatch.setattr(history_module, "select", fake_select)

    resp = client.get("/api/v1/history?page=1&page_size=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_more"] is True
    assert body["page"] == 1
    assert len(body["items"]) == 10
    first = body["items"][0]
    assert first["id"] == 1
    assert first["input_type"] == "ctf"
    assert len(first["input_text"]) == 120  # 摘要截断
    assert "tokens_out" in first and "created_at" in first
    assert captured["table"] == "analyses"
    assert captured["params"]["user_id"] == "eq.u1"
    assert captured["params"]["order"] == "created_at.desc"
    assert captured["params"]["limit"] == "11"
    assert captured["params"]["offset"] == "0"


def test_history_detail_found(logged_in, monkeypatch):
    async def fake_select(table, *, select_fields="*", params=None, http_client=None):
        assert params["id"] == "eq.42"
        assert params["user_id"] == "eq.u1"  # 归属校验
        return [ROW]

    monkeypatch.setattr(history_module, "select", fake_select)

    resp = client.get("/api/v1/history/42")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert body["result_md"] == "## 分析\n内容"
    assert body["input_text"] == "flag{" + "x" * 200 + "}"  # 详情不截断


def test_history_detail_not_found_404(logged_in, monkeypatch):
    async def fake_select(table, *, select_fields="*", params=None, http_client=None):
        return []

    monkeypatch.setattr(history_module, "select", fake_select)

    resp = client.get("/api/v1/history/999")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "not_found"


def test_history_supabase_down_503(logged_in, monkeypatch):
    async def boom(table, *, select_fields="*", params=None, http_client=None):
        raise SupabaseUnavailable("down")

    monkeypatch.setattr(history_module, "select", boom)

    resp = client.get("/api/v1/history")
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "supabase_unavailable"


def test_history_requires_login():
    resp = client.get("/api/v1/history")
    assert resp.status_code == 401
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_plans_route.py tests/test_user_profile_route.py tests/test_history_route.py -q`

Expected: 失败（routes 不存在 → 404/导入错误）。

- [ ] **Step 3: 实现三个路由**

新建 `backend/app/api/routes/plans.py`：

```python
from fastapi import APIRouter

from app.services.plans import PRICING_PLANS

router = APIRouter(tags=["plans"])


@router.get("/plans")
async def list_plans():
    """定价配置单一数据源：前端定价页与升级卡片消费。"""
    return {"plans": PRICING_PLANS}
```

新建 `backend/app/api/routes/user.py`：

```python
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import UserIdentity, require_user
from app.services.plans import PLAN_LIMITS
from app.services.supabase_rest import SupabaseUnavailable
from app.services.usage import get_usage, resolve_plan

router = APIRouter(tags=["user"])


@router.get("/user/profile")
async def get_profile(user: UserIdentity = Depends(require_user)):
    """当前用户画像：套餐、今日已用、限额、剩余。"""
    try:
        plan = await resolve_plan(user.id)
        used = await get_usage(user.id)
    except SupabaseUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "supabase_unavailable", "message": "用户服务暂时不可用，请稍后重试。"},
        ) from exc
    limit = PLAN_LIMITS[plan]
    return {
        "email": user.email,
        "plan": plan,
        "used_today": used,
        "limit": limit,
        "remaining": max(0, limit - used),
    }
```

新建 `backend/app/api/routes/history.py`：

```python
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import UserIdentity, require_user
from app.services.supabase_rest import SupabaseUnavailable, select

router = APIRouter(tags=["history"])

_LIST_FIELDS = "id,input_type,input_text,result_md,model,tokens_in,tokens_out,created_at"
_SUMMARY_LEN = 120


@router.get("/history")
async def list_history(
    user: UserIdentity = Depends(require_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    """本人分析记录，时间倒序；多取 1 条判断 has_more，input_text 输出 120 字摘要。"""
    try:
        rows = await select(
            "analyses",
            select_fields=_LIST_FIELDS,
            params={
                "user_id": f"eq.{user.id}",
                "order": "created_at.desc",
                "limit": str(page_size + 1),
                "offset": str((page - 1) * page_size),
            },
        )
    except SupabaseUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "supabase_unavailable", "message": "历史服务暂时不可用，请稍后重试。"},
        ) from exc
    has_more = len(rows) > page_size
    return {
        "items": [
            {
                "id": int(r["id"]),
                "input_type": r.get("input_type"),
                "input_text": (r.get("input_text") or "")[:_SUMMARY_LEN],
                "tokens_out": int(r.get("tokens_out") or 0),
                "created_at": r.get("created_at"),
            }
            for r in rows[:page_size]
        ],
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
    }


@router.get("/history/{analysis_id}")
async def get_history(analysis_id: int, user: UserIdentity = Depends(require_user)):
    """单条详情；同时按 user_id 过滤保证仅本人可见（他人记录等同不存在）。"""
    try:
        rows = await select(
            "analyses",
            select_fields=_LIST_FIELDS,
            params={"id": f"eq.{analysis_id}", "user_id": f"eq.{user.id}"},
        )
    except SupabaseUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "supabase_unavailable", "message": "历史服务暂时不可用，请稍后重试。"},
        ) from exc
    if not rows:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "记录不存在。"},
        )
    r = rows[0]
    return {
        "id": int(r["id"]),
        "input_type": r.get("input_type"),
        "input_text": r.get("input_text"),
        "result_md": r.get("result_md") or "",
        "model": r.get("model"),
        "tokens_in": int(r.get("tokens_in") or 0),
        "tokens_out": int(r.get("tokens_out") or 0),
        "created_at": r.get("created_at"),
    }
```

修改 `backend/app/main.py`：导入行改为

```python
from app.api.routes import analysis, health, history, plans, user
```

并追加注册：

```python
app.include_router(health.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_plans_route.py tests/test_user_profile_route.py tests/test_history_route.py -q`

Expected: 9 passed（1 plans + 3 user + 5 history）。

- [ ] **Step 5: 全量回归**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`

Expected: 110 passed（101 + 9）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/plans.py backend/app/api/routes/user.py backend/app/api/routes/history.py backend/app/main.py backend/tests/test_plans_route.py backend/tests/test_user_profile_route.py backend/tests/test_history_route.py
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(backend): plans/user/profile/history 三个新路由并注册"
```

---

### Task 9: analysis.py 登录/匿名双分支改造（TDD）

**Files:**
- Modify: `backend/app/api/routes/analysis.py`
- Modify: `backend/tests/test_analysis_route.py`

- [ ] **Step 1: 补失败测试**

在 `backend/tests/test_analysis_route.py` 中：

1. 顶部 import 区追加：

```python
from app.api.deps import UserIdentity, get_optional_user
from app.services.supabase_rest import SupabaseUnavailable
```

2. 在 `fresh_limiter` fixture 后追加登录用户 fixture：

```python
@pytest.fixture
def logged_in_user():
    app.dependency_overrides[get_optional_user] = lambda: UserIdentity(id="user-123", email="a@b.c")
    yield
    app.dependency_overrides.clear()
```

3. 文件末尾追加测试：

```python
def _stub_usage(monkeypatch, *, resolve_result="free", increment_result=True):
    async def fake_resolve(user_id):
        return resolve_result

    async def fake_increment(user_id, limit):
        return increment_result

    monkeypatch.setattr(analysis_module, "resolve_plan", fake_resolve)
    monkeypatch.setattr(analysis_module, "check_and_increment", fake_increment)


def test_logged_in_skips_ip_limit_and_records_user_id(monkeypatch, logged_in_user):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()
    reset_limiter()

    transport, _ = make_streaming_transport(["ok"])
    provider = OpenAICompatProvider(
        base_url="https://mock.local/v1", api_key="k", model="deepseek-chat",
        http_client=httpx.AsyncClient(transport=transport),
    )
    monkeypatch.setattr(analysis_module, "get_provider", lambda: provider)
    _stub_usage(monkeypatch)
    recorded: dict = {}

    async def fake_record(**kwargs):
        recorded.update(kwargs)
        return 7

    monkeypatch.setattr(analysis_module, "record_analysis", fake_record)

    payload = {"input_text": "TCP 三次握手的过程是怎样的？"}
    first = client.post("/api/v1/analysis", json=payload)
    second = client.post("/api/v1/analysis", json=payload)
    # 登录用户跳过 IP 限流（limit=1 也放行）
    assert first.status_code == 200
    assert second.status_code == 200
    assert recorded["user_id"] == "user-123"
    assert parse_sse(first.text)[-1][0] == "done"


def test_quota_exceeded_returns_429_json(monkeypatch, logged_in_user):
    _stub_usage(monkeypatch, increment_result=False)

    resp = client.post("/api/v1/analysis", json={"input_text": "什么是 SQL 注入？"})
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"] == "quota_exceeded"
    assert "升级" in resp.json()["detail"]["message"]
    assert resp.headers["content-type"].startswith("application/json")  # 非 SSE


def test_supabase_down_returns_503(monkeypatch, logged_in_user):
    async def boom(user_id):
        raise SupabaseUnavailable("down")

    monkeypatch.setattr(analysis_module, "resolve_plan", boom)

    resp = client.post("/api/v1/analysis", json={"input_text": "什么是 SQL 注入？"})
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "supabase_unavailable"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_analysis_route.py::test_logged_in_skips_ip_limit_and_records_user_id tests/test_analysis_route.py::test_quota_exceeded_returns_429_json tests/test_analysis_route.py::test_supabase_down_returns_503 -q`

Expected: FAIL（analysis_module 尚无 resolve_plan / check_and_increment，登录分支不存在）。

- [ ] **Step 3: 重写 analysis.py**

用以下完整内容覆盖 `backend/app/api/routes/analysis.py`：

```python
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.deps import UserIdentity, get_optional_user
from app.providers.base import ProviderError
from app.providers.factory import get_provider
from app.prompts.system_prompts import SYSTEM_PROMPTS
from app.schemas.analysis import AnalysisRequest
from app.services.input_classifier import classify
from app.services.plans import PLAN_LIMITS
from app.services.rate_limiter import get_limiter
from app.services.recorder import record_analysis
from app.services.safety import check_safety
from app.services.supabase_rest import SupabaseUnavailable
from app.services.tokens import estimate_tokens
from app.services.usage import check_and_increment, resolve_plan

router = APIRouter(tags=["analysis"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/analysis")
async def analyze(
    payload: AnalysisRequest,
    request: Request,
    user: UserIdentity | None = Depends(get_optional_user),
):
    # 安全护栏对登录与匿名用户一视同仁（合规红线）
    safety = check_safety(payload.input_text)
    if not safety.ok:
        raise HTTPException(
            status_code=400,
            detail={"code": "refused", "message": safety.refusal},
        )

    if user is not None:
        # 登录用户：个人配额（跳过 IP 限流），流开始前原子扣减，防流中断白嫖
        try:
            plan = await resolve_plan(user.id)
        except SupabaseUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": "supabase_unavailable", "message": "配额服务暂时不可用，请稍后重试。"},
            ) from exc
        limit = PLAN_LIMITS[plan]
        try:
            incremented = await check_and_increment(user.id, limit)
        except SupabaseUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": "supabase_unavailable", "message": "配额服务暂时不可用，请稍后重试。"},
            ) from exc
        if not incremented:
            message = (
                "今日分析次数已达上限（Pro 200 次/天），请明天再试。"
                if plan == "pro"
                else "今日免费额度已用完，升级 Pro 解锁更多次数。"
            )
            raise HTTPException(
                status_code=429,
                detail={"code": "quota_exceeded", "message": message},
            )
    else:
        # 匿名用户：IP 限流兜底（阶段3 行为不变）
        ip = _client_ip(request)
        if not get_limiter().allow(ip):
            raise HTTPException(
                status_code=429,
                detail={"code": "rate_limited", "message": "请求过于频繁，请稍后再试。"},
            )

    input_type = classify(payload.input_text)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS[input_type]},
        {"role": "user", "content": payload.input_text},
    ]
    user_id = user.id if user else None

    async def gen() -> AsyncIterator[str]:
        chunks: list[str] = []
        try:
            yield _sse("meta", {"input_type": input_type})
            provider = get_provider()
            async for chunk in provider.stream_chat(messages):
                chunks.append(chunk)
                yield _sse("delta", {"content": chunk})
            full = "".join(chunks)
            tokens_out = estimate_tokens(full)
            analysis_id = await record_analysis(
                input_type=input_type,
                input_text=payload.input_text,
                result_md=full,
                model=provider.model,
                tokens_in=estimate_tokens(payload.input_text),
                tokens_out=tokens_out,
                user_id=user_id,
            )
            yield _sse("done", {"analysis_id": analysis_id, "tokens_out": tokens_out})
        except ProviderError as exc:
            yield _sse("error", {"code": "provider_error", "message": f"AI 服务暂时不可用：{exc}"})
        except Exception as exc:  # noqa: BLE001 — 流中途异常统一转为 error 事件，不输出输入内容
            print(f"[SecMate] analysis stream error: {exc!r}")
            yield _sse("error", {"code": "internal_error", "message": "分析过程中出现异常，请稍后重试。"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
```

- [ ] **Step 4: 运行 analysis 全部测试**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_analysis_route.py -q`

Expected: 8 passed（原 5 + 新 3；原有匿名测试行为不变）。

- [ ] **Step 5: 全量回归**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`

Expected: 全部通过（约 95 个）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/analysis.py backend/tests/test_analysis_route.py
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(backend): 分析路由登录分支——个人配额原子扣减，匿名路径不变"
```

---

### Task 10: 后端全量回归 + 真实 Supabase 联调（检查点，需 0.1 节前置条件）

**Files:** 无代码改动。

- [ ] **Step 1: 全量回归**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`

Expected: 全部通过。

- [ ] **Step 2: 确认前置条件**

确认用户已完成 0.1 节两项（schema.sql 已执行、Confirm email 已关闭）。验证 profiles 表已建：

```bash
curl -s -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" "https://<PROJECT_REF>.supabase.co/rest/v1/profiles?select=id&limit=1"
```

Expected: 返回 `[]`（不再是 PGRST205）。

- [ ] **Step 3: 启动后端**（若未运行）

Run: `cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --port 8001`（后台运行）

- [ ] **Step 4: 注册测试用户拿 token**

```bash
curl -s -X POST "https://<PROJECT_REF>.supabase.co/auth/v1/signup" \
  -H "apikey: $NEXT_PUBLIC_SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"dev1@example.com","password":"devpass123"}'
```

Expected: 响应含 `access_token`（Confirm email 已关闭）。记录 `TOKEN=...`。

- [ ] **Step 5: 逐项 curl 验证**

```bash
TOKEN=<上一步 access_token>

# 1) 定价配置
curl -s http://localhost:8001/api/v1/plans
# 预期：{"plans":[4 个方案]}

# 2) 用户画像（首次：used_today=0, remaining=5）
curl -s http://localhost:8001/api/v1/user/profile -H "Authorization: Bearer $TOKEN"
# 预期：{"email":"dev1@example.com","plan":"free","used_today":0,"limit":5,"remaining":5}

# 3) 历史（首次为空）
curl -s "http://localhost:8001/api/v1/history?page=1" -H "Authorization: Bearer $TOKEN"
# 预期：{"items":[],"page":1,"page_size":10,"has_more":false}

# 4) 一次真实分析（流式，约 10-40 秒）
curl -sN -X POST http://localhost:8001/api/v1/analysis \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"input_text":"什么是 SQL 注入？"}'
# 预期：meta → delta… → done(analysis_id 非空)

# 5) 再次画像：used_today 应 +1
curl -s http://localhost:8001/api/v1/user/profile -H "Authorization: Bearer $TOKEN"

# 6) 历史应有 1 条，详情可查
curl -s "http://localhost:8001/api/v1/history?page=1" -H "Authorization: Bearer $TOKEN"
curl -s "http://localhost:8001/api/v1/history/1" -H "Authorization: Bearer $TOKEN"

# 7) 无效 token → 401
curl -s http://localhost:8001/api/v1/user/profile -H "Authorization: Bearer bad.token.here"
# 预期：401 invalid_token
```

- [ ] **Step 6: 记录联调结果到任务描述**

全部符合预期才进入前端任务；任何失败按 systematic-debugging 排查（重点：schema.sql 是否执行、RPC 函数是否存在）。

---

### Task 11: 前端 Supabase 客户端与 AuthProvider

**Files:**
- Modify: `frontend/package.json`（npm install 自动更新）
- Create: `frontend/src/lib/supabase.ts`
- Create: `frontend/src/lib/auth.tsx`
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: 安装依赖**

Run: `cd frontend && npm install @supabase/supabase-js`

Expected: 安装成功，package.json 增加 `"@supabase/supabase-js"`。

- [ ] **Step 2: 创建 supabase.ts**

新建 `frontend/src/lib/supabase.ts`：

```ts
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// 未配置时为 null：构建/预览环境可正常渲染，登录功能提示「未配置」
const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const supabase: SupabaseClient | null =
  url && anonKey ? createClient(url, anonKey) : null;
```

- [ ] **Step 3: 创建 auth.tsx**

新建 `frontend/src/lib/auth.tsx`：

```tsx
"use client";

import { createContext, useContext, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";

import { supabase } from "@/lib/supabase";

interface AuthState {
  session: Session | null;
  loading: boolean;
}

const AuthContext = createContext<AuthState>({ session: null, loading: true });

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!supabase) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    supabase.auth.getSession().then(({ data }) => {
      if (!cancelled) {
        setSession(data.session);
        setLoading(false);
      }
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      if (!cancelled) setSession(s);
    });
    return () => {
      cancelled = true;
      sub.subscription.unsubscribe();
    };
  }, []);

  return (
    <AuthContext.Provider value={{ session, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
```

- [ ] **Step 4: layout.tsx 挂载 AuthProvider**

修改 `frontend/src/app/layout.tsx`：

```tsx
import type { Metadata } from "next";
import localFont from "next/font/local";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";

// geistSans / geistMono 定义与 metadata 保持不变……

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 5: build 与 lint 验证**

Run: `cd frontend && npm run build && npm run lint`

Expected: 构建成功、lint 零错误。

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/supabase.ts frontend/src/lib/auth.tsx frontend/src/app/layout.tsx
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(frontend): Supabase 客户端与全局 AuthProvider（localStorage 会话）"
```

---

### Task 12: 前端 api.ts 扩展 + 代理路由（analyze 透传 + [...path]）

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/api/analyze/route.ts`
- Create: `frontend/src/app/api/[...path]/route.ts`

- [ ] **Step 1: 扩展 api.ts**

在 `frontend/src/lib/api.ts` 顶部 import 区追加：

```ts
import { supabase } from "@/lib/supabase";
```

在 `ApiError` 类定义之后追加类型与函数：

```ts
export interface UserProfile {
  email: string | null;
  plan: "free" | "pro";
  used_today: number;
  limit: number;
  remaining: number;
}

export interface HistoryItem {
  id: number;
  input_type: string;
  input_text: string;
  tokens_out: number;
  created_at: string;
}

export interface HistoryDetail {
  id: number;
  input_type: string;
  input_text: string;
  result_md: string;
  model: string | null;
  tokens_in: number;
  tokens_out: number;
  created_at: string;
}

export interface HistoryPage {
  items: HistoryItem[];
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface PricingPlan {
  id: string;
  name: string;
  price: number;
  price_unit: string;
  description: string;
  features: string[];
  highlighted: boolean;
  cta_text: string;
  coming_soon: boolean;
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    if (data.session) {
      headers["Authorization"] = `Bearer ${data.session.access_token}`;
    }
  }
  return headers;
}

async function fetchJson<T>(path: string): Promise<T> {
  const headers = await getAuthHeaders();
  const resp = await fetch(path, { headers });
  if (resp.status === 401) {
    // 登录已过期：清除本地会话，由页面跳转 /login
    await supabase?.auth.signOut();
    throw new ApiError("invalid_token", "登录已过期，请重新登录。");
  }
  if (!resp.ok) {
    let code = "unknown";
    let message = `请求失败（HTTP ${resp.status}）`;
    try {
      const body = await resp.json();
      const detail = body.detail ?? body;
      code = detail.code ?? code;
      message = detail.message ?? message;
    } catch {
      // 非 JSON 错误体，保留默认文案
    }
    throw new ApiError(code, message);
  }
  return (await resp.json()) as T;
}

export function fetchProfile(): Promise<UserProfile> {
  return fetchJson<UserProfile>("/api/user/profile");
}

export function fetchPlans(): Promise<{ plans: PricingPlan[] }> {
  return fetchJson<{ plans: PricingPlan[] }>("/api/plans");
}

export function fetchHistory(page: number, pageSize = 10): Promise<HistoryPage> {
  return fetchJson<HistoryPage>(`/api/history?page=${page}&page_size=${pageSize}`);
}

export function fetchHistoryDetail(id: number): Promise<HistoryDetail> {
  return fetchJson<HistoryDetail>(`/api/history/${id}`);
}

export function notifyQuotaRefresh() {
  window.dispatchEvent(new Event("secmate:quota-refresh"));
}
```

修改 `streamAnalysis` 的 fetch 调用，加上 Authorization：

```ts
export async function streamAnalysis(
  inputText: string,
  inputType: InputType | null,
  cb: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const headers = await getAuthHeaders();
  const resp = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ input_text: inputText, input_type: inputType }),
    signal,
  });
  // ……其余保持不变
}
```

- [ ] **Step 2: /api/analyze 路由透传 Authorization**

修改 `frontend/src/app/api/analyze/route.ts` 的 POST 处理：

```ts
import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// 架构约定：前端代理后端（隐藏后端地址、统一 CORS、SSE 透传）
const BACKEND_API_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify({ detail: { code: "invalid_request", message: "请求体不是合法 JSON" } }),
      { status: 400, headers: { "Content-Type": "application/json; charset=utf-8" } },
    );
  }

  const upstreamHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Forwarded-For":
      request.headers.get("x-forwarded-for") ||
      request.headers.get("x-real-ip") ||
      "127.0.0.1",
  };
  const auth = request.headers.get("authorization");
  if (auth) upstreamHeaders["Authorization"] = auth;

  const upstream = await fetch(`${BACKEND_API_URL}/api/v1/analysis`, {
    method: "POST",
    headers: upstreamHeaders,
    body: JSON.stringify(body),
    signal: request.signal,
  });

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text();
    return new Response(
      text || JSON.stringify({ detail: { code: "upstream_error", message: "后端服务不可用，请稍后重试" } }),
      { status: upstream.status, headers: { "Content-Type": "application/json; charset=utf-8" } },
    );
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
```

- [ ] **Step 3: 创建 [...path] 通用代理**

新建 `frontend/src/app/api/[...path]/route.ts`：

```ts
import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_API_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

// GET-only 白名单代理：plans / user/profile / history*
// （POST /api/analyze 由静态路由处理，优先级高于本 catch-all）
const ALLOWED_PREFIXES = ["plans", "user/profile", "history"];

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } },
) {
  const path = params.path.join("/");
  const allowed = ALLOWED_PREFIXES.some(
    (p) => path === p || path.startsWith(`${p}/`),
  );
  if (!allowed) {
    return new Response(
      JSON.stringify({ detail: { code: "not_found", message: "接口不存在" } }),
      { status: 404, headers: { "Content-Type": "application/json; charset=utf-8" } },
    );
  }

  const headers: Record<string, string> = {
    "X-Forwarded-For":
      request.headers.get("x-forwarded-for") ||
      request.headers.get("x-real-ip") ||
      "127.0.0.1",
  };
  const auth = request.headers.get("authorization");
  if (auth) headers["Authorization"] = auth;

  const upstream = await fetch(
    `${BACKEND_API_URL}/api/v1/${path}${request.nextUrl.search}`,
    { headers, signal: request.signal },
  );
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
```

- [ ] **Step 4: build 与 lint 验证**

Run: `cd frontend && npm run build && npm run lint`

Expected: 构建成功、lint 零错误。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/app/api/analyze/route.ts frontend/src/app/api/\[...path\]/route.ts
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(frontend): API 封装带 Bearer 透传与 GET 白名单通用代理"
```

---

### Task 13: 前端 UserMenu + QuotaBadge + SiteHeader 集成

**Files:**
- Create: `frontend/src/components/quota-badge.tsx`
- Create: `frontend/src/components/user-menu.tsx`
- Modify: `frontend/src/components/site-header.tsx`

- [ ] **Step 1: 创建 quota-badge.tsx**

新建 `frontend/src/components/quota-badge.tsx`：

```tsx
"use client";

import { useEffect, useState } from "react";

import { fetchProfile, type UserProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function QuotaBadge() {
  const { session } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);

  useEffect(() => {
    if (!session) {
      setProfile(null);
      return;
    }
    let cancelled = false;
    async function load() {
      try {
        const p = await fetchProfile();
        if (!cancelled) setProfile(p);
      } catch {
        // 401/503 等：徽章静默不显示（401 已由 fetchJson 触发全局登出）
      }
    }
    load();
    window.addEventListener("secmate:quota-refresh", load);
    return () => {
      cancelled = true;
      window.removeEventListener("secmate:quota-refresh", load);
    };
  }, [session]);

  if (!session || !profile) return null;
  return (
    <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
      今日剩余 {profile.remaining} 次
    </span>
  );
}
```

- [ ] **Step 2: 创建 user-menu.tsx**

新建 `frontend/src/components/user-menu.tsx`：

```tsx
"use client";

import Link from "next/link";
import { CreditCard, History, LogOut } from "lucide-react";

import { QuotaBadge } from "@/components/quota-badge";
import { buttonVariants } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { supabase } from "@/lib/supabase";

export function UserMenu() {
  const { session, loading } = useAuth();

  if (loading) {
    return <div className="h-8 w-20 animate-pulse rounded-lg bg-muted" />;
  }
  if (!session) {
    return (
      <Link href="/login" className={buttonVariants({ variant: "outline", size: "sm" })}>
        登录
      </Link>
    );
  }
  const email = session.user.email ?? "已登录";

  async function signOut() {
    await supabase?.auth.signOut();
  }

  return (
    <div className="group relative">
      <button className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-1.5 text-sm transition-colors hover:bg-muted">
        <span className="max-w-40 truncate">{email}</span>
        <QuotaBadge />
      </button>
      <div className="invisible absolute right-0 top-full z-50 mt-1 w-44 rounded-lg border border-border bg-popover p-1 opacity-0 shadow-md transition-all group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100">
        <Link
          href="/history"
          className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm transition-colors hover:bg-muted"
        >
          <History className="size-4" />
          分析历史
        </Link>
        <Link
          href="/pricing"
          className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm transition-colors hover:bg-muted"
        >
          <CreditCard className="size-4" />
          定价与升级
        </Link>
        <button
          onClick={signOut}
          className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-sm transition-colors hover:bg-muted"
        >
          <LogOut className="size-4" />
          退出登录
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: site-header.tsx 集成 UserMenu**

修改 `frontend/src/components/site-header.tsx`：

```tsx
import Link from "next/link";
import { ShieldCheck } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/user-menu";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <ShieldCheck className="size-5 text-emerald-500" />
          <span>SecMate</span>
        </Link>
        <nav className="flex items-center gap-3">
          <Link
            href="/analyze"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            开始分析
          </Link>
          <UserMenu />
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: build 与 lint 验证**

Run: `cd frontend && npm run build && npm run lint`

Expected: 构建成功、lint 零错误。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/quota-badge.tsx frontend/src/components/user-menu.tsx frontend/src/components/site-header.tsx
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(frontend): header 用户菜单与今日配额徽章"
```

---

### Task 14: 前端登录/注册页

**Files:**
- Create: `frontend/src/app/login/page.tsx`

- [ ] **Step 1: 创建登录页**

新建 `frontend/src/app/login/page.tsx`：

```tsx
"use client";

import { LogIn } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { supabase } from "@/lib/supabase";

type Mode = "signin" | "signup";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!supabase) {
      setError("登录服务未配置，请联系管理员。");
      return;
    }
    setSubmitting(true);
    setError(null);
    const { error: err } =
      mode === "signin"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password });
    setSubmitting(false);
    if (err) {
      const msg = err.message.toLowerCase();
      if (msg.includes("already registered")) {
        setError("该邮箱已注册，请直接登录。");
      } else if (msg.includes("invalid login credentials")) {
        setError("邮箱或密码错误。");
      } else {
        setError(err.message);
      }
      return;
    }
    router.push("/analyze");
  }

  async function githubLogin() {
    if (!supabase) {
      setError("登录服务未配置，请联系管理员。");
      return;
    }
    const { error: err } = await supabase.auth.signInWithOAuth({
      provider: "github",
      options: { redirectTo: `${window.location.origin}/analyze` },
    });
    if (err) setError("GitHub 登录方式未配置，请使用邮箱登录。");
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-md px-4 py-16">
        <div className="rounded-xl border border-border bg-card/60 p-6">
          <h1 className="text-xl font-bold">
            {mode === "signin" ? "登录 SecMate" : "注册 SecMate"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {mode === "signin"
              ? "登录后解锁每日 5 次个人配额与历史记录"
              : "注册即可获得每日 5 次免费分析额度"}
          </p>
          {error && (
            <div className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <form onSubmit={submit} className="mt-4 space-y-3">
            <label className="block">
              <span className="text-sm font-medium">邮箱</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                placeholder="you@example.com"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium">密码</span>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                placeholder="至少 8 位"
              />
            </label>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "请稍候…" : mode === "signin" ? "登录" : "注册"}
            </Button>
          </form>
          <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground">
            <div className="h-px flex-1 bg-border" />
            或
            <div className="h-px flex-1 bg-border" />
          </div>
          <Button variant="outline" className="w-full" onClick={githubLogin}>
            <LogIn />
            使用 GitHub 登录
          </Button>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            {mode === "signin" ? "还没有账号？" : "已有账号？"}
            <button
              className="ml-1 text-primary hover:underline"
              onClick={() => {
                setMode(mode === "signin" ? "signup" : "signin");
                setError(null);
              }}
            >
              {mode === "signin" ? "立即注册" : "去登录"}
            </button>
          </p>
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 2: build 与 lint 验证**

Run: `cd frontend && npm run build && npm run lint`

Expected: 构建成功、lint 零错误。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/login/page.tsx
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(frontend): 登录/注册页（邮箱密码 + GitHub OAuth 按钮）"
```

---

### Task 15: 前端定价页

**Files:**
- Create: `frontend/src/app/pricing/page.tsx`

- [ ] **Step 1: 创建定价页**

新建 `frontend/src/app/pricing/page.tsx`：

```tsx
"use client";

import { useEffect, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { fetchPlans, type PricingPlan } from "@/lib/api";

export default function PricingPage() {
  const [plans, setPlans] = useState<PricingPlan[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchPlans()
      .then((data) => {
        if (!cancelled) setPlans(data.plans);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-4 py-12">
        <h1 className="text-center text-3xl font-bold tracking-tight">
          选择适合你的方案
        </h1>
        <p className="mx-auto mt-2 max-w-xl text-center text-sm text-muted-foreground">
          SecMate 定价（支付功能即将上线，当前仅支持 Free 方案）
        </p>
        {error && (
          <p className="mt-6 text-center text-sm text-destructive">{error}</p>
        )}
        {plans ? (
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {plans.map((plan) => (
              <div
                key={plan.id}
                className={`flex flex-col rounded-xl border p-5 ${
                  plan.highlighted
                    ? "border-emerald-500/50 bg-emerald-500/5"
                    : "border-border bg-card/60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold">{plan.name}</h2>
                  {plan.highlighted && (
                    <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-600 dark:text-emerald-400">
                      推荐
                    </span>
                  )}
                </div>
                <div className="mt-3">
                  <span className="text-3xl font-bold">
                    {plan.price === 0 ? "¥0" : `¥${plan.price}`}
                  </span>
                  <span className="ml-1 text-sm text-muted-foreground">
                    {plan.price_unit}
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {plan.description}
                </p>
                <ul className="mt-4 flex-1 space-y-2 text-sm">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2">
                      <span className="mt-1.5 size-1 shrink-0 rounded-full bg-emerald-500" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Button
                  variant={plan.highlighted ? "default" : "outline"}
                  className="mt-5 w-full"
                  disabled={plan.coming_soon}
                >
                  {plan.cta_text}
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-10 text-center text-sm text-muted-foreground">
            正在加载方案…
          </p>
        )}
      </main>
    </div>
  );
}
```

- [ ] **Step 2: build 与 lint 验证**

Run: `cd frontend && npm run build && npm run lint`

Expected: 构建成功、lint 零错误。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pricing/page.tsx
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(frontend): 定价页（四档方案卡，数据来自 /api/plans，升级按钮即将上线）"
```

---

### Task 16: 前端历史列表与详情页

**Files:**
- Create: `frontend/src/app/history/page.tsx`
- Create: `frontend/src/app/history/[id]/page.tsx`

- [ ] **Step 1: 创建历史列表页**

新建 `frontend/src/app/history/page.tsx`：

```tsx
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { ApiError, fetchHistory, type HistoryItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { INPUT_TYPE_LABELS, type InputType } from "@/lib/input-classifier";

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", { hour12: false });
}

function typeLabel(t: string): string {
  return INPUT_TYPE_LABELS[t as InputType] ?? t;
}

export default function HistoryPage() {
  const router = useRouter();
  const { session, loading } = useAuth();
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !session) {
      router.replace("/login");
    }
  }, [loading, session, router]);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    fetchHistory(1)
      .then((data) => {
        if (cancelled) return;
        setItems(data.items);
        setHasMore(data.has_more);
        setPage(1);
      })
      .catch((e: Error) => {
        if (!cancelled) {
          if (e instanceof ApiError && e.code === "invalid_token") {
            router.replace("/login");
          } else {
            setError(e.message);
          }
        }
      });
    return () => {
      cancelled = true;
    };
  }, [session, router]);

  async function loadMore() {
    const next = page + 1;
    try {
      const data = await fetchHistory(next);
      setItems((prev) => [...(prev ?? []), ...data.items]);
      setHasMore(data.has_more);
      setPage(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    }
  }

  if (loading || !session) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <SiteHeader />
        <main className="mx-auto max-w-4xl px-4 py-16 text-center text-sm text-muted-foreground">
          加载中…
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-4xl space-y-4 px-4 py-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">分析历史</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            你的全部分析记录（仅本人可见）
          </p>
        </div>
        {error && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
        {items === null ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            正在加载…
          </p>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-border bg-card/60 p-10 text-center">
            <p className="text-sm text-muted-foreground">
              还没有分析记录，去
              <Link href="/analyze" className="mx-1 text-primary hover:underline">
                开始分析
              </Link>
              吧。
            </p>
          </div>
        ) : (
          <>
            <ul className="space-y-3">
              {items.map((item) => (
                <li key={item.id}>
                  <Link
                    href={`/history/${item.id}`}
                    className="block rounded-xl border border-border bg-card/60 p-4 transition-colors hover:border-emerald-500/40"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                        {typeLabel(item.input_type)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {formatTime(item.created_at)}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 break-all text-sm text-foreground/80">
                      {item.input_text || "（空输入）"}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
            {hasMore && (
              <div className="flex justify-center">
                <Button variant="outline" size="sm" onClick={loadMore}>
                  加载更多
                </Button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
```

- [ ] **Step 2: 创建历史详情页**

新建 `frontend/src/app/history/[id]/page.tsx`：

```tsx
"use client";

import { Check, Copy } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Markdown } from "@/components/markdown";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { ApiError, fetchHistoryDetail, type HistoryDetail } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { INPUT_TYPE_LABELS, type InputType } from "@/lib/input-classifier";

export default function HistoryDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { session, loading } = useAuth();
  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!loading && !session) {
      router.replace("/login");
    }
  }, [loading, session, router]);

  useEffect(() => {
    if (!session || !params.id) return;
    let cancelled = false;
    fetchHistoryDetail(Number(params.id))
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((e: Error) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.code === "invalid_token") {
          router.replace("/login");
        } else {
          setError(e.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [session, params.id, router]);

  async function copyAll() {
    if (!detail) return;
    try {
      await navigator.clipboard.writeText(detail.result_md);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 剪贴板不可用时静默失败
    }
  }

  if (loading || !session) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <SiteHeader />
        <main className="mx-auto max-w-4xl px-4 py-16 text-center text-sm text-muted-foreground">
          加载中…
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-4xl space-y-4 px-4 py-8">
        {error && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
        {detail && (
          <>
            <div className="rounded-xl border border-border bg-card/60 p-5">
              <div className="flex items-center justify-between">
                <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                  {INPUT_TYPE_LABELS[detail.input_type as InputType] ?? detail.input_type}
                </span>
                <Button variant="outline" size="sm" onClick={copyAll}>
                  {copied ? <Check className="text-emerald-500" /> : <Copy />}
                  {copied ? "已复制" : "复制全文"}
                </Button>
              </div>
              <h2 className="mt-3 text-sm font-medium text-muted-foreground">
                原始输入
              </h2>
              <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-lg border border-border bg-background p-3 font-mono text-xs leading-relaxed">
                {detail.input_text}
              </pre>
            </div>
            <div className="rounded-xl border border-border bg-card/60 p-5">
              <h2 className="mb-4 border-b border-border pb-3 text-sm font-medium">
                分析结果
              </h2>
              {detail.result_md ? (
                <Markdown content={detail.result_md} />
              ) : (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  该记录没有结果内容（可能生成中断）。
                </p>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
```

- [ ] **Step 3: build 与 lint 验证**

Run: `cd frontend && npm run build && npm run lint`

Expected: 构建成功、lint 零错误。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/history/page.tsx "frontend/src/app/history/[id]/page.tsx"
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(frontend): 分析历史列表与详情页（未登录重定向 /login）"
```

---

### Task 17: 前端 UpgradeCard + analyze-client 集成

**Files:**
- Create: `frontend/src/components/upgrade-card.tsx`
- Modify: `frontend/src/components/analyze-client.tsx`

- [ ] **Step 1: 创建 upgrade-card.tsx**

新建 `frontend/src/components/upgrade-card.tsx`：

```tsx
import Link from "next/link";
import { Crown } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";

export function UpgradeCard() {
  return (
    <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/5 p-6 text-center">
      <Crown className="mx-auto size-8 text-emerald-500" />
      <h3 className="mt-3 text-lg font-semibold">今日免费额度已用完</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Free 方案每日 5 次分析。升级 Pro 解锁每日 200 次与完整历史记录。
      </p>
      <Link href="/pricing" className={buttonVariants({ className: "mt-4" })}>
        查看 Pro 定价
      </Link>
    </div>
  );
}
```

- [ ] **Step 2: 修改 analyze-client.tsx**

修改 `frontend/src/components/analyze-client.tsx`：

1. import 追加：

```tsx
import { UpgradeCard } from "@/components/upgrade-card";
import { ApiError, notifyQuotaRefresh, streamAnalysis } from "@/lib/api";
```

（原 `import { ApiError, streamAnalysis } from "@/lib/api";` 替换为上面这一行。）

2. 状态追加（在 `const [error, setError] = useState<string | null>(null);` 之后）：

```tsx
const [quotaExceeded, setQuotaExceeded] = useState(false);
```

3. `handleAnalyze` 中：开头加 `setQuotaExceeded(false);`；`onDone` 改为：

```tsx
onDone: () => {
  setStatus("done");
  notifyQuotaRefresh();
},
```

4. catch 分支改为：

```tsx
} catch (err) {
  if ((err as Error).name !== "AbortError") {
    if (err instanceof ApiError && err.code === "quota_exceeded") {
      setQuotaExceeded(true);
      setStatus("idle");
    } else {
      setError(err instanceof ApiError ? err.message : "网络错误，请稍后重试");
      setStatus("error");
    }
  }
}
```

5. 渲染区：在 `{error && (...)}` 块之后、`<AnalysisInput ...>` 之前插入：

```tsx
{quotaExceeded && <UpgradeCard />}
```

（`AnalysisInput` 需在 quotaExceeded 时隐藏或保持可见均可，保持可见即可。）

- [ ] **Step 3: build 与 lint 验证**

Run: `cd frontend && npm run build && npm run lint`

Expected: 构建成功、lint 零错误。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/upgrade-card.tsx frontend/src/components/analyze-client.tsx
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "feat(frontend): 配额耗尽升级引导卡片与配额徽章刷新事件"
```

---

### Task 18: 浏览器 E2E 集成验证（检查点，需 0.1 节前置条件）

**Files:**
- Create: `e2e/phase4.py`

- [ ] **Step 1: 确认前置条件与环境**

- 0.1 节两项已完成（schema.sql 已执行、Confirm email 已关闭）。
- 后端运行中：`http://localhost:8001`（backend/.env 已含密钥）。
- 前端运行中：`http://localhost:3000`（`cd frontend && npm run dev`）。
- 若两者未运行：`python "C:\Users\22145\.agents\skills\webapp-testing\scripts\with_server.py" --server "cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --port 8001" --port 8001 --server "cd frontend && npm run dev" --port 3000 -- python e2e/phase4.py`（webapp-testing skill）。

- [ ] **Step 2: 创建 E2E 脚本**

新建 `e2e/phase4.py`：

```python
import time

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
EMAIL = f"e2e-{int(time.time())}@example.com"
PASSWORD = "secmate-e2e-123"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # 1. 注册
    page.goto(f"{BASE}/login")
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="立即注册").click()
    page.get_by_placeholder("you@example.com").fill(EMAIL)
    page.get_by_placeholder("至少 8 位").fill(PASSWORD)
    page.get_by_role("button", name="注册", exact=True).click()
    page.wait_for_url("**/analyze", timeout=20000)
    print("[1/6] 注册并跳转分析页 OK")

    # 2. header 显示配额徽章
    page.wait_for_selector("text=今日剩余", timeout=15000)
    print("[2/6] 配额徽章显示 OK")

    def run_analysis(wait_done: bool):
        page.goto(f"{BASE}/analyze")
        page.wait_for_load_state("networkidle")
        page.get_by_role("textbox").fill("什么是 SQL 注入？")
        page.get_by_role("button", name="开始分析").click()
        if wait_done:
            page.wait_for_selector(
                "text=以上内容仅供授权环境下的学习与防御研究使用。",
                timeout=120000,
            )
        else:
            page.wait_for_timeout(4000)  # 配额在流开始前已扣减，中断也计数

    # 3. 前 2 次完整跑完（供历史断言），再快速消耗 3 次
    run_analysis(wait_done=True)
    run_analysis(wait_done=True)
    run_analysis(wait_done=False)
    run_analysis(wait_done=False)
    run_analysis(wait_done=False)
    print("[3/6] 5 次分析已消耗配额 OK")

    # 4. 第 6 次：出现升级引导卡片
    page.goto(f"{BASE}/analyze")
    page.wait_for_load_state("networkidle")
    page.get_by_role("textbox").fill("什么是 SQL 注入？")
    page.get_by_role("button", name="开始分析").click()
    page.wait_for_selector("text=今日免费额度已用完", timeout=15000)
    print("[4/6] 第 6 次触发升级卡片 OK")

    # 5. 历史列表与详情
    page.goto(f"{BASE}/history")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("a[href^='/history/']", timeout=15000)
    print("[5/6] 历史列表有记录 OK")
    page.locator("a[href^='/history/']").first.click()
    page.wait_for_selector("text=分析结果", timeout=15000)
    print("[6/6] 历史详情渲染 OK")

    # 6. 退出登录回匿名态
    page.goto(f"{BASE}/analyze")
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name=EMAIL).hover()
    page.get_by_role("button", name="退出登录").click()
    page.wait_for_selector("a[href='/login']", timeout=15000)
    print("[7/7] 退出登录回匿名态 OK")

    browser.close()
    print("E2E PASS")
```

（若 2 次完整分析耗时过长，可改为 1 次完整 + 4 次快速消耗，历史断言只需 ≥1 条。）

- [ ] **Step 3: 运行 E2E**

Run: `cd "D:\ku\VScode\Saas" && python e2e/phase4.py`

Expected: 依次打印 7 个 OK 与 `E2E PASS`。

- [ ] **Step 4: 失败排查**

任一断言失败按 systematic-debugging 排查。常见点：schema.sql 未执行（profile 接口 503/500）、Confirm email 未关（注册后不跳转）、后端未带 .env 启动（匿名路径误入 IP 限流）。

- [ ] **Step 5: Commit**

```bash
git add e2e/phase4.py
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "test(e2e): 阶段4 全链路 Playwright 验证脚本"
```

---

### Task 19: 文档与环境变量样例收尾

**Files:**
- Modify: `backend/.env.example`
- Modify: `frontend/.env.local.example`
- Modify: `README.md`

- [ ] **Step 1: 更新 backend/.env.example**

把末尾的 Supabase 段替换为：

```
# Supabase（阶段4 用户系统；未配置时后端退化为纯匿名模式）
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
# 本地验签 JWT 所需（Dashboard → Project Settings → API Keys → JWT Secret）
SUPABASE_JWT_SECRET=
```

- [ ] **Step 2: 更新 frontend/.env.local.example**

在文件末尾追加：

```
# Supabase（登录注册用 publishable key，仅限浏览器使用）
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

- [ ] **Step 3: README.md 追加阶段4 说明**

先 Read `README.md` 了解结构，然后在末尾追加以下小节（若已有类似小节则合并）：

```markdown
## 阶段4（商业化）已上线

- 邮箱注册/登录（Supabase Auth，JWT 由后端本地验签），GitHub OAuth 按钮预留（需在 Supabase 配置 GitHub provider）
- Free 5 次/天个人配额（Postgres RPC 原子扣减），Pro 200 次/天上限代码路径就绪
- 分析历史（列表 + 详情，仅本人可见）
- 定价页四档方案（数据来自 `GET /api/v1/plans`），支付接口预留，升级按钮「即将上线」
- 匿名分析保持可用（IP 限流兜底，Supabase 未配置时全链路降级）

**上线前需在 Supabase 完成：** SQL Editor 执行 `database/schema.sql`；Authentication → Email → 关闭 Confirm email。

**新环境变量：** 后端 `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_JWT_SECRET`；前端 `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`。
```

- [ ] **Step 4: 最终回归（最低验收门槛）**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`

Expected: 全部通过。

Run: `cd frontend && npm run build && npm run lint`

Expected: 构建成功、lint 零错误。

- [ ] **Step 5: Commit**

```bash
git add backend/.env.example frontend/.env.local.example README.md
git -c user.name=Zzzhan999 -c user.email=Zzzhan999@outlook.com commit -m "docs: 阶段4 环境变量样例与 README 功能说明"
```

---

## 验收对照（设计文档第 9 节）

| # | 验收标准 | 对应任务 |
|---|---------|---------|
| 1 | 匿名路径与阶段3 一致 | T9（现有测试不改仍通过）+ T10 Step 1 |
| 2 | 注册→登录→5 次分析→第 6 次被拒 + 升级引导 | T10（curl 联调）+ T18（E2E） |
| 3 | 配额徽章实时正确 | T13 + T17（done 事件后刷新）+ T18 |
| 4 | 历史列表/详情仅本人可见 | T8（后端 user_id 过滤）+ T16 + T18 |
| 5 | 定价页四卡、升级按钮「即将上线」 | T5 + T8 + T15 |
| 6 | pytest 全绿 + 前端 build/lint 零错误 + E2E 通过 | T10 / T18 / T19 Step 4 |

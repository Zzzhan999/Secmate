import asyncio
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from starlette.requests import Request

from app.api.deps import get_optional_user, require_user
from app.core.config import get_settings
from app.core.security import reset_verifier

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


def test_require_user_with_invalid_token_401():
    # 带 token 但无效：必须走 invalid_token（401），而非 unauthorized
    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_user(make_request("Bearer not-a-jwt")))
    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "invalid_token"


def test_token_when_supabase_unconfigured_503():
    # conftest 已清空 Supabase 配置：带 RS256 token 无法拉取 JWKS → 503
    reset_verifier()  # 防其他测试污染全局验签器缓存，保证与执行顺序无关
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(_payload(), key, algorithm="RS256", headers={"kid": "k"})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_optional_user(make_request(f"Bearer {token}")))
    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "supabase_unavailable"

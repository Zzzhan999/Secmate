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
    # 预热缓存：第一次拉取返回空 JWKS，并把拉取时间拨回超过刷新阈值
    verifier._keys = asyncio.run(verifier._fetch_jwks())
    verifier._fetched_at = time.monotonic() - verifier.REFRESH_MIN_INTERVAL - 1
    token = jwt.encode(_payload(), key, algorithm="RS256", headers={"kid": "rsa-kid"})
    payload = asyncio.run(verifier.verify(token))
    assert payload["sub"] == "user-123"
    assert calls["count"] == 2  # 预热 1 次 + 未命中后刷新 1 次


def test_jwks_fetch_http_error_raises_jwks_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    get_settings.cache_clear()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    verifier = SupabaseTokenVerifier(http_client=client)
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


def test_jwks_kid_miss_within_interval_does_not_refetch(monkeypatch):
    # 防拉取放大：缓存新鲜时未知 kid 不再触发外呼
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier, calls = _verifier_with_jwks(monkeypatch, [[_rsa_jwk(key)]])
    token = jwt.encode(_payload(), key, algorithm="RS256", headers={"kid": "other-kid"})
    with pytest.raises(jwt.InvalidKeyError):
        asyncio.run(verifier.verify(token))
    assert calls["count"] == 1


def test_alg_key_type_mismatch_rejected(monkeypatch):
    # 头声明 RS256 但 kid 指向 EC 密钥：必须报 PyJWTError（401），而非裸 TypeError（500）
    key = ec.generate_private_key(ec.SECP256R1())
    verifier, _ = _verifier_with_jwks(monkeypatch, [[_ec_jwk(key)]])
    token = jwt.encode(_payload(), key, algorithm="ES256", headers={"kid": "ec-kid"})
    header, payload, sig = token.split(".")
    forged = ".".join([_b64u(json.dumps({"alg": "RS256", "typ": "JWT", "kid": "ec-kid"}).encode()), payload, sig])
    with pytest.raises(jwt.PyJWTError):
        asyncio.run(verifier.verify(forged))


def test_hs256_fresh_token_within_leeway_passes(configured_hs256):
    # Supabase 签发时钟略快于本机：新 token 的 iat 会比本机时间早几秒，须用 leeway 容忍
    token = jwt.encode(_payload(iat=int(time.time()) + 30), "test-secret", algorithm="HS256")
    payload = asyncio.run(SupabaseTokenVerifier().verify(token))
    assert payload["sub"] == "user-123"


def test_hs256_too_far_in_future_iat_rejected(configured_hs256):
    token = jwt.encode(_payload(iat=int(time.time()) + 120), "test-secret", algorithm="HS256")
    with pytest.raises(jwt.ImmatureSignatureError):
        asyncio.run(SupabaseTokenVerifier().verify(token))

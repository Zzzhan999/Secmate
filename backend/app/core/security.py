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

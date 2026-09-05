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

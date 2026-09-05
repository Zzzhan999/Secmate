"""个人配额：套餐解析（profiles.plan + subscriptions 校验）与 RPC 原子扣减。"""

from datetime import datetime, timezone

from app.services.plans import PLAN_LIMITS
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
    if plan not in PLAN_LIMITS:
        plan = "free"  # 数据库异常值兜底为 free，避免上层 PLAN_LIMITS KeyError
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

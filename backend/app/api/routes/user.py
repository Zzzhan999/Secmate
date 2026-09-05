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

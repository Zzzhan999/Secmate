from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """健康检查：部署探针与前端联调用。"""
    s = get_settings()
    return {"status": "ok", "app": s.app_name, "version": s.app_version, "environment": s.environment}

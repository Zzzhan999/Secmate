from fastapi import APIRouter

from app.services.plans import PRICING_PLANS

router = APIRouter(tags=["plans"])


@router.get("/plans")
async def list_plans():
    """定价配置单一数据源：前端定价页与升级卡片消费。"""
    return {"plans": PRICING_PLANS}

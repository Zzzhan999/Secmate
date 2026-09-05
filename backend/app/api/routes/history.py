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

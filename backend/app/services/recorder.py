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

import httpx

from app.core.config import get_settings

_REST_PATH = "/rest/v1"


class SupabaseUnavailable(Exception):
    """Supabase 未配置或请求失败。认证/配额/历史路径的上层转 503。"""


def _headers() -> dict[str, str]:
    s = get_settings()
    return {
        "apikey": s.supabase_service_role_key,
        "Authorization": f"Bearer {s.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


async def _request(
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    json_body: dict | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> httpx.Response:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        raise SupabaseUnavailable("Supabase 未配置")
    url = f"{s.supabase_url.rstrip('/')}{_REST_PATH}{path}"

    async def _call(client: httpx.AsyncClient) -> httpx.Response:
        try:
            return await client.request(method, url, params=params, json=json_body, headers=_headers())
        except httpx.HTTPError as exc:
            raise SupabaseUnavailable(f"Supabase 请求失败: {exc}") from exc

    if http_client is not None:
        resp = await _call(http_client)
    else:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await _call(client)
    if resp.status_code >= 400:
        raise SupabaseUnavailable(f"Supabase 返回 {resp.status_code}")
    return resp


async def select(
    table: str,
    *,
    select_fields: str = "*",
    params: dict[str, str] | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """GET /rest/v1/{table}?select=... 返回行数组（service_role 绕过 RLS）。"""
    all_params = {"select": select_fields, **(params or {})}
    resp = await _request("GET", f"/{table}", params=all_params, http_client=http_client)
    return resp.json()


async def rpc(
    fn_name: str,
    args: dict,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list | int | None:
    """POST /rest/v1/rpc/{fn}。标量函数返回标量，集合函数返回数组，无行返回 []。"""
    resp = await _request("POST", f"/rpc/{fn_name}", json_body=args, http_client=http_client)
    if not resp.content:
        return []
    return resp.json()

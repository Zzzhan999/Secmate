import asyncio
import json

import httpx
import pytest

from app.core.config import get_settings
from app.services.supabase_rest import SupabaseUnavailable, rpc, select


def test_unconfigured_raises_unavailable():
    with pytest.raises(SupabaseUnavailable):
        asyncio.run(select("profiles"))


def test_rpc_sends_service_role_headers(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=6)

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(
        rpc("check_and_increment_usage", {"p_user_id": "u1", "p_limit": 5}, http_client=client)
    )
    assert result == 6
    assert captured["url"].endswith("/rest/v1/rpc/check_and_increment_usage")
    assert captured["headers"]["apikey"] == "svc-key"
    assert captured["headers"]["authorization"] == "Bearer svc-key"
    assert captured["body"] == {"p_user_id": "u1", "p_limit": 5}


def test_rpc_empty_body_returns_empty_list(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(
        rpc("check_and_increment_usage", {"p_user_id": "u1", "p_limit": 5}, http_client=client)
    )
    assert result == []


def test_select_builds_query_params(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=[{"plan": "free"}])

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    rows = asyncio.run(
        select(
            "profiles",
            select_fields="plan",
            params={"id": "eq.u1"},
            http_client=client,
        )
    )
    assert rows == [{"plan": "free"}]
    assert captured["url"].startswith("https://xyzcompany.supabase.co/rest/v1/profiles")
    assert "select=plan" in captured["url"]
    assert "id=eq.u1" in captured["url"]


def test_http_error_raises_unavailable(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(SupabaseUnavailable):
        asyncio.run(select("profiles", http_client=client))

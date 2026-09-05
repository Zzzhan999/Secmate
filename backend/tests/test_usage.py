import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.core.config import get_settings
from app.services.usage import check_and_increment, get_usage, resolve_plan

NOW = datetime.now(timezone.utc)


def _client(monkeypatch, routes: dict[str, list | int]):
    """routes: profiles/subscriptions/daily_usage/rpc 各自返回的 JSON 或 "empty"（空响应体）。"""
    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/rpc/" in url:
            body = routes.get("rpc")
            if body == "empty":
                return httpx.Response(200, content=b"")
            return httpx.Response(200, json=body)
        if "profiles" in url:
            return httpx.Response(200, json=routes.get("profiles", []))
        if "subscriptions" in url:
            return httpx.Response(200, json=routes.get("subscriptions", []))
        if "daily_usage" in url:
            return httpx.Response(200, json=routes.get("daily_usage", []))
        return httpx.Response(404, json={})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_resolve_plan_free_fast_path(monkeypatch):
    client = _client(monkeypatch, {"profiles": [{"plan": "free"}]})
    plan = asyncio.run(resolve_plan("u1", http_client=client))
    assert plan == "free"


def test_resolve_plan_missing_profile_defaults_free(monkeypatch):
    client = _client(monkeypatch, {"profiles": []})
    plan = asyncio.run(resolve_plan("u1", http_client=client))
    assert plan == "free"


def test_resolve_plan_pro_with_active_unexpired_sub(monkeypatch):
    future = (NOW + timedelta(days=30)).isoformat()
    client = _client(
        monkeypatch,
        {"profiles": [{"plan": "pro"}], "subscriptions": [{"status": "active", "expires_at": future}]},
    )
    plan = asyncio.run(resolve_plan("u1", http_client=client))
    assert plan == "pro"


def test_resolve_plan_pro_with_no_expiry_stays_pro(monkeypatch):
    client = _client(
        monkeypatch,
        {"profiles": [{"plan": "pro"}], "subscriptions": [{"status": "active", "expires_at": None}]},
    )
    plan = asyncio.run(resolve_plan("u1", http_client=client))
    assert plan == "pro"


def test_resolve_plan_pro_with_expired_sub_falls_back_free(monkeypatch):
    past = (NOW - timedelta(days=1)).isoformat()
    client = _client(
        monkeypatch,
        {"profiles": [{"plan": "pro"}], "subscriptions": [{"status": "active", "expires_at": past}]},
    )
    plan = asyncio.run(resolve_plan("u1", http_client=client))
    assert plan == "free"


def test_resolve_plan_pro_without_sub_falls_back_free(monkeypatch):
    client = _client(monkeypatch, {"profiles": [{"plan": "pro"}], "subscriptions": []})
    plan = asyncio.run(resolve_plan("u1", http_client=client))
    assert plan == "free"


def test_check_and_increment_success(monkeypatch):
    client = _client(monkeypatch, {"rpc": 6})
    ok = asyncio.run(check_and_increment("u1", 5, http_client=client))
    assert ok is True


def test_check_and_increment_quota_exceeded(monkeypatch):
    client = _client(monkeypatch, {"rpc": "empty"})
    ok = asyncio.run(check_and_increment("u1", 5, http_client=client))
    assert ok is False


def test_get_usage_returns_count(monkeypatch):
    client = _client(monkeypatch, {"daily_usage": [{"count": 3}]})
    used = asyncio.run(get_usage("u1", http_client=client))
    assert used == 3


def test_get_usage_zero_when_no_row(monkeypatch):
    client = _client(monkeypatch, {"daily_usage": []})
    used = asyncio.run(get_usage("u1", http_client=client))
    assert used == 0


def test_resolve_plan_unknown_plan_falls_back_free(monkeypatch):
    client = _client(monkeypatch, {"profiles": [{"plan": "premium"}]})
    plan = asyncio.run(resolve_plan("u1", http_client=client))
    assert plan == "free"

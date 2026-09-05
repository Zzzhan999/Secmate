import asyncio
import json

import httpx
import pytest

from app.core.config import get_settings
from app.services.recorder import record_analysis


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_skips_when_supabase_not_configured():
    result = asyncio.run(record_analysis(
        input_type="general", input_text="hi", result_md="ok",
        model="deepseek-chat", tokens_in=1, tokens_out=1,
    ))
    assert result is None


def test_posts_to_postgrest_with_service_role(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{"id": 42}])

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key-123")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(record_analysis(
        input_type="http", input_text="GET / HTTP/1.1", result_md="ok",
        model="deepseek-chat", tokens_in=10, tokens_out=20, http_client=client,
    ))

    assert result == 42
    assert captured["url"].endswith("/rest/v1/analyses")
    assert captured["headers"]["apikey"] == "service-role-key-123"
    assert captured["headers"]["authorization"] == "Bearer service-role-key-123"
    assert captured["body"]["input_type"] == "http"
    assert captured["body"]["user_id"] is None
    assert captured["body"]["result_md"] == "ok"


def test_db_failure_returns_none(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key-123")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(record_analysis(
        input_type="general", input_text="hi", result_md="ok",
        model="deepseek-chat", tokens_in=1, tokens_out=1, http_client=client,
    ))
    assert result is None


def test_posts_user_id_when_logged_in(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{"id": 99}])

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key-123")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(record_analysis(
        input_type="general", input_text="hi", result_md="ok",
        model="deepseek-chat", tokens_in=1, tokens_out=1,
        user_id="user-123", http_client=client,
    ))
    assert result == 99
    assert captured["body"]["user_id"] == "user-123"

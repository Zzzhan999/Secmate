import pytest
from fastapi.testclient import TestClient

import app.api.routes.history as history_module
from app.api.deps import UserIdentity, require_user
from app.main import app
from app.services.supabase_rest import SupabaseUnavailable

client = TestClient(app)

ROW = {
    "id": 1,
    "input_type": "ctf",
    "input_text": "flag{" + "x" * 200 + "}",
    "result_md": "## 分析\n内容",
    "model": "glm-4-flash",
    "tokens_in": 30,
    "tokens_out": 100,
    "created_at": "2026-09-05T10:00:00+00:00",
}


@pytest.fixture
def logged_in():
    app.dependency_overrides[require_user] = lambda: UserIdentity(id="u1", email="a@b.c")
    yield
    app.dependency_overrides.clear()


def test_list_history_with_has_more(logged_in, monkeypatch):
    captured: dict = {}

    async def fake_select(table, *, select_fields="*", params=None, http_client=None):
        captured["table"] = table
        captured["params"] = params
        return [dict(ROW, id=i) for i in range(1, 12)]  # 多取 1 条 → has_more=True

    monkeypatch.setattr(history_module, "select", fake_select)

    resp = client.get("/api/v1/history?page=1&page_size=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_more"] is True
    assert body["page"] == 1
    assert len(body["items"]) == 10
    first = body["items"][0]
    assert first["id"] == 1
    assert first["input_type"] == "ctf"
    assert len(first["input_text"]) == 120  # 摘要截断
    assert "tokens_out" in first and "created_at" in first
    assert captured["table"] == "analyses"
    assert captured["params"]["user_id"] == "eq.u1"
    assert captured["params"]["order"] == "created_at.desc"
    assert captured["params"]["limit"] == "11"
    assert captured["params"]["offset"] == "0"


def test_history_detail_found(logged_in, monkeypatch):
    async def fake_select(table, *, select_fields="*", params=None, http_client=None):
        assert params["id"] == "eq.42"
        assert params["user_id"] == "eq.u1"  # 归属校验
        return [ROW]

    monkeypatch.setattr(history_module, "select", fake_select)

    resp = client.get("/api/v1/history/42")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert body["result_md"] == "## 分析\n内容"
    assert body["input_text"] == "flag{" + "x" * 200 + "}"  # 详情不截断


def test_history_detail_not_found_404(logged_in, monkeypatch):
    async def fake_select(table, *, select_fields="*", params=None, http_client=None):
        return []

    monkeypatch.setattr(history_module, "select", fake_select)

    resp = client.get("/api/v1/history/999")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "not_found"


def test_history_supabase_down_503(logged_in, monkeypatch):
    async def boom(table, *, select_fields="*", params=None, http_client=None):
        raise SupabaseUnavailable("down")

    monkeypatch.setattr(history_module, "select", boom)

    resp = client.get("/api/v1/history")
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "supabase_unavailable"


def test_history_requires_login():
    resp = client.get("/api/v1/history")
    assert resp.status_code == 401

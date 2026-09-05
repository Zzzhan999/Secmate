import pytest
from fastapi.testclient import TestClient

import app.api.routes.user as user_module
from app.api.deps import UserIdentity, require_user
from app.main import app
from app.services.supabase_rest import SupabaseUnavailable

client = TestClient(app)


@pytest.fixture
def logged_in():
    app.dependency_overrides[require_user] = lambda: UserIdentity(id="u1", email="a@b.c")
    yield
    app.dependency_overrides.clear()


def test_profile_shape(logged_in, monkeypatch):
    async def fake_resolve(user_id):
        return "free"

    async def fake_usage(user_id):
        return 3

    monkeypatch.setattr(user_module, "resolve_plan", fake_resolve)
    monkeypatch.setattr(user_module, "get_usage", fake_usage)

    resp = client.get("/api/v1/user/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"email": "a@b.c", "plan": "free", "used_today": 3, "limit": 5, "remaining": 2}


def test_profile_supabase_down_returns_503(logged_in, monkeypatch):
    async def boom(user_id):
        raise SupabaseUnavailable("down")

    monkeypatch.setattr(user_module, "resolve_plan", boom)

    resp = client.get("/api/v1/user/profile")
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "supabase_unavailable"


def test_profile_requires_login():
    resp = client.get("/api/v1/user/profile")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "unauthorized"

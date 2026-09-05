from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_plans_returns_four_plans():
    resp = client.get("/api/v1/plans")
    assert resp.status_code == 200
    plans = resp.json()["plans"]
    assert len(plans) == 4
    assert plans[0]["id"] == "free"
    assert any(p["coming_soon"] for p in plans)

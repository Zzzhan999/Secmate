from app.services.plans import PLAN_LIMITS, PRICING_PLANS


def test_plan_limits():
    assert PLAN_LIMITS == {"free": 5, "pro": 200}


def test_pricing_has_four_plans():
    assert len(PRICING_PLANS) == 4
    ids = [p["id"] for p in PRICING_PLANS]
    assert ids == ["free", "pro_monthly", "pro_yearly", "pro_student"]


def test_only_pro_plans_marked_coming_soon():
    free = next(p for p in PRICING_PLANS if p["id"] == "free")
    assert free["coming_soon"] is False
    assert free["cta_text"] == "当前方案"
    for p in PRICING_PLANS:
        if p["id"] != "free":
            assert p["coming_soon"] is True
            assert p["cta_text"] == "即将上线"

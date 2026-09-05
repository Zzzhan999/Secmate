import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def hermetic_env(monkeypatch):
    """测试环境隔离：清除 Supabase 配置，避免本地 .env 已配置时误连真实云端。"""
    for var in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

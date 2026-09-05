import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def hermetic_env(monkeypatch):
    """测试环境隔离：将 Supabase 配置置空，避免本地 .env 已配置时误连真实云端。

    注意必须用 setenv("") 而非 delenv：pydantic-settings 在 os.environ 无该变量时会回退读 .env 文件，
    delenv 挡不住 .env 里的真实凭据（实测会打到真实云端）。
    """
    for var in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        monkeypatch.setenv(var, "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

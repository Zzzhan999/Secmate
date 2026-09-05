from app.core.config import get_settings


def test_supabase_settings_are_empty_in_tests():
    """本地 .env 即使配置了真实 Supabase 凭据，测试环境也必须读到空值。"""
    settings = get_settings()
    assert settings.supabase_url == ""
    assert settings.supabase_service_role_key == ""
    assert settings.supabase_jwt_secret == ""

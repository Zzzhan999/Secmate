from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置：从 backend/.env 读取，部署时可用平台环境变量覆盖。"""

    app_name: str = "SecMate API"
    app_version: str = "0.1.0"
    environment: str = "development"

    # CORS：逗号分隔的多个来源，如 "http://localhost:3000,https://secmate.app"
    cors_origins: list[str] = ["http://localhost:3000"]

    # AI Provider：openai_compat 一套协议覆盖 DeepSeek / OpenAI / Ollama(/v1)
    ai_provider: str = "openai_compat"
    ai_base_url: str = "https://api.deepseek.com/v1"
    ai_api_key: str = ""
    ai_model: str = "deepseek-chat"

    # 限流：每 IP 每分钟允许的分析请求数
    rate_limit_per_minute: int = 10

    # Supabase（阶段4 用户系统启用；现在可留空）
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """单例配置：测试中可用 get_settings.cache_clear() 重置。"""
    return Settings()

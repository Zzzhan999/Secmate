from app.core.config import get_settings
from app.providers.base import BaseProvider
from app.providers.openai_compat import OpenAICompatProvider


def get_provider() -> BaseProvider:
    """按配置创建 AI 提供商实例；新增提供商（如 Claude）只需在此注册。"""
    s = get_settings()
    if s.ai_provider == "openai_compat":
        return OpenAICompatProvider(base_url=s.ai_base_url, api_key=s.ai_api_key, model=s.ai_model)
    raise ValueError(f"不支持的 AI_PROVIDER: {s.ai_provider}")

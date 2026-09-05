from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class ProviderError(Exception):
    """AI 提供商调用失败（鉴权/网络/限流等）的统一异常，上层据此返回 502。"""


class BaseProvider(ABC):
    """AI 提供商统一抽象：所有实现以流式文本产出，供上层增量渲染。"""

    model: str

    @abstractmethod
    def stream_chat(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """流式对话，逐段产出文本增量。messages 为 OpenAI 格式 [{role, content}]。"""

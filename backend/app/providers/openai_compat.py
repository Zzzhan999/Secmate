import json
from collections.abc import AsyncIterator

import httpx

from app.providers.base import BaseProvider, ProviderError


class OpenAICompatProvider(BaseProvider):
    """OpenAI 兼容协议实现：一个实现覆盖 DeepSeek / OpenAI / Ollama(/v1) / vLLM。"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._http_client = http_client  # 测试注入 MockTransport 用
        self._timeout = timeout

    async def stream_chat(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        payload = {"model": self.model, "messages": messages, "stream": True}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async def _stream(client: httpx.AsyncClient) -> AsyncIterator[str]:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self._timeout,
                ) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode("utf-8", errors="replace")
                        raise ProviderError(f"AI 提供商返回 {resp.status_code}: {body[:500]}")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue  # 忽略无法解析的心跳行
                        delta = (chunk.get("choices") or [{}])[0].get("delta") or {}
                        content = delta.get("content")
                        if content:
                            yield content
            except httpx.HTTPError as exc:
                raise ProviderError(f"AI 提供商连接失败: {exc}") from exc

        if self._http_client is not None:
            async for token in _stream(self._http_client):
                yield token
        else:
            async with httpx.AsyncClient() as client:
                async for token in _stream(client):
                    yield token

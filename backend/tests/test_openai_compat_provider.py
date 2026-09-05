import json

import httpx
import pytest

from app.providers.base import ProviderError
from app.providers.openai_compat import OpenAICompatProvider


def _sse_handler(request: httpx.Request) -> httpx.Response:
    chunks = [
        {"choices": [{"delta": {"content": "你好"}}]},
        {"choices": [{"delta": {"content": "，"}}]},
        {"choices": [{"delta": {"content": "世界"}}]},
    ]
    body = "".join(f"data: {json.dumps(c, ensure_ascii=False)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    return httpx.Response(200, content=body.encode("utf-8"), headers={"content-type": "text/event-stream"})


def _error_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(401, json={"error": "invalid api key"})


async def test_stream_chat_yields_tokens():
    client = httpx.AsyncClient(transport=httpx.MockTransport(_sse_handler))
    provider = OpenAICompatProvider(
        base_url="https://example.com/v1", api_key="sk-test", model="deepseek-chat", http_client=client
    )
    tokens = [t async for t in provider.stream_chat([{"role": "user", "content": "hi"}])]
    assert "".join(tokens) == "你好，世界"


async def test_stream_chat_raises_provider_error_on_http_error():
    client = httpx.AsyncClient(transport=httpx.MockTransport(_error_handler))
    provider = OpenAICompatProvider(
        base_url="https://example.com/v1", api_key="sk-bad", model="deepseek-chat", http_client=client
    )
    with pytest.raises(ProviderError):
        async for _ in provider.stream_chat([{"role": "user", "content": "hi"}]):
            pass

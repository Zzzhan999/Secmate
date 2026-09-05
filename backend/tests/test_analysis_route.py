import json

import httpx
import pytest
from fastapi.testclient import TestClient

import app.api.routes.analysis as analysis_module
from app.core.config import get_settings
from app.main import app
from app.providers.openai_compat import OpenAICompatProvider
from app.services.rate_limiter import reset_limiter

client = TestClient(app)


def make_streaming_transport(chunks: list[str], status: int = 200) -> httpx.MockTransport:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        captured["url"] = str(request.url)

        def body() -> bytes:
            for c in chunks:
                chunk = {"choices": [{"delta": {"content": c}}]}
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode()
            yield b"data: [DONE]\n\n"

        return httpx.Response(
            status,
            headers={"content-type": "text/event-stream"},
            content=b"".join(body()),
        )

    return httpx.MockTransport(handler), captured


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.split("\n\n"):
        event = data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if event and data is not None:
            events.append((event, data))
    return events


@pytest.fixture(autouse=True)
def fresh_limiter(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_PER_MINUTE", raising=False)
    get_settings.cache_clear()
    reset_limiter()
    yield
    reset_limiter()
    get_settings.cache_clear()


def test_analysis_streams_meta_delta_done(monkeypatch):
    transport, captured = make_streaming_transport(["你", "好，世界"])
    provider = OpenAICompatProvider(
        base_url="https://mock.local/v1", api_key="k", model="deepseek-chat",
        http_client=httpx.AsyncClient(transport=transport),
    )
    monkeypatch.setattr(analysis_module, "get_provider", lambda: provider)

    resp = client.post("/api/v1/analysis", json={
        "input_text": "POST /login HTTP/1.1\nHost: 192.168.1.10\nUser-Agent: curl/8.0",
    })
    assert resp.status_code == 200
    events = parse_sse(resp.text)
    assert events[0][0] == "meta"
    assert events[0][1]["input_type"] == "http"
    deltas = [d["content"] for e, d in events if e == "delta"]
    assert "".join(deltas) == "你好，世界"
    assert events[-1][0] == "done"

    # 系统提示词为 http 场景且包含安全红线；用户输入原样透传
    messages = captured["payload"]["messages"]
    assert messages[0]["role"] == "system"
    assert "HTTP" in messages[0]["content"]
    assert "授权环境" in messages[0]["content"]
    assert messages[1]["content"].startswith("POST /login")


def test_sensitive_input_refused_with_400():
    resp = client.post("/api/v1/analysis", json={
        "input_text": "我的手机号 13812341234，帮忙分析这个报错",
    })
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "refused"
    assert "敏感信息" in resp.json()["detail"]["message"]


def test_rate_limit_returns_429(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()
    reset_limiter()
    transport, _ = make_streaming_transport(["ok"])
    provider = OpenAICompatProvider(
        base_url="https://mock.local/v1", api_key="k", model="deepseek-chat",
        http_client=httpx.AsyncClient(transport=transport),
    )
    monkeypatch.setattr(analysis_module, "get_provider", lambda: provider)

    payload = {"input_text": "TCP 三次握手的过程是怎样的？", "input_type": "protocol"}
    first = client.post("/api/v1/analysis", json=payload)
    second = client.post("/api/v1/analysis", json=payload)
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"]["code"] == "rate_limited"


def test_provider_error_emits_error_event(monkeypatch):
    transport, _ = make_streaming_transport([], status=401)
    provider = OpenAICompatProvider(
        base_url="https://mock.local/v1", api_key="k", model="deepseek-chat",
        http_client=httpx.AsyncClient(transport=transport),
    )
    monkeypatch.setattr(analysis_module, "get_provider", lambda: provider)

    resp = client.post("/api/v1/analysis", json={"input_text": "什么是 SQL 注入？"})
    assert resp.status_code == 200
    events = parse_sse(resp.text)
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "provider_error"


def test_too_long_input_rejected():
    resp = client.post("/api/v1/analysis", json={"input_text": "a" * 8001})
    assert resp.status_code == 422

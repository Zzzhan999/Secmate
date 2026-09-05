import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.providers.base import ProviderError
from app.providers.factory import get_provider
from app.prompts.system_prompts import SYSTEM_PROMPTS
from app.schemas.analysis import AnalysisRequest
from app.services.input_classifier import classify
from app.services.rate_limiter import get_limiter
from app.services.recorder import record_analysis
from app.services.safety import check_safety
from app.services.tokens import estimate_tokens

router = APIRouter(tags=["analysis"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/analysis")
async def analyze(payload: AnalysisRequest, request: Request):
    ip = _client_ip(request)

    if not get_limiter().allow(ip):
        raise HTTPException(
            status_code=429,
            detail={"code": "rate_limited", "message": "请求过于频繁，请稍后再试。"},
        )

    safety = check_safety(payload.input_text)
    if not safety.ok:
        raise HTTPException(
            status_code=400,
            detail={"code": "refused", "message": safety.refusal},
        )

    input_type = classify(payload.input_text)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS[input_type]},
        {"role": "user", "content": payload.input_text},
    ]

    async def gen() -> AsyncIterator[str]:
        chunks: list[str] = []
        try:
            yield _sse("meta", {"input_type": input_type})
            provider = get_provider()
            async for chunk in provider.stream_chat(messages):
                chunks.append(chunk)
                yield _sse("delta", {"content": chunk})
            full = "".join(chunks)
            tokens_out = estimate_tokens(full)
            analysis_id = await record_analysis(
                input_type=input_type,
                input_text=payload.input_text,
                result_md=full,
                model=provider.model,
                tokens_in=estimate_tokens(payload.input_text),
                tokens_out=tokens_out,
            )
            yield _sse("done", {"analysis_id": analysis_id, "tokens_out": tokens_out})
        except ProviderError as exc:
            yield _sse("error", {"code": "provider_error", "message": f"AI 服务暂时不可用：{exc}"})
        except Exception as exc:  # noqa: BLE001 — 流中途异常统一转为 error 事件，不输出输入内容
            print(f"[SecMate] analysis stream error: {exc!r}")
            yield _sse("error", {"code": "internal_error", "message": "分析过程中出现异常，请稍后重试。"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

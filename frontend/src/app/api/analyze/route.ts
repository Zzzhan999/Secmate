import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// 架构约定：前端代理后端（隐藏后端地址、统一 CORS、SSE 透传）
const BACKEND_API_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify({ detail: { code: "invalid_request", message: "请求体不是合法 JSON" } }),
      { status: 400, headers: { "Content-Type": "application/json; charset=utf-8" } },
    );
  }

  const upstream = await fetch(`${BACKEND_API_URL}/api/v1/analysis`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Forwarded-For":
        request.headers.get("x-forwarded-for") ||
        request.headers.get("x-real-ip") ||
        "127.0.0.1",
    },
    body: JSON.stringify(body),
    signal: request.signal,
  });

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text();
    return new Response(
      text || JSON.stringify({ detail: { code: "upstream_error", message: "后端服务不可用，请稍后重试" } }),
      { status: upstream.status, headers: { "Content-Type": "application/json; charset=utf-8" } },
    );
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}

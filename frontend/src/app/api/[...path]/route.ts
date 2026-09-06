import { NextRequest } from "next/server";

import { validateProxyPath } from "@/lib/proxy-path";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_API_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

// GET-only 白名单代理：plans / user/profile / history*
// （POST /api/analyze 由静态路由处理，优先级高于本 catch-all）
export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } },
) {
  const path = validateProxyPath(params.path);
  if (path === null) {
    return new Response(
      JSON.stringify({ detail: { code: "not_found", message: "接口不存在" } }),
      { status: 404, headers: { "Content-Type": "application/json; charset=utf-8" } },
    );
  }

  const headers: Record<string, string> = {
    "X-Forwarded-For":
      request.headers.get("x-forwarded-for") ||
      request.headers.get("x-real-ip") ||
      "127.0.0.1",
  };
  const auth = request.headers.get("authorization");
  if (auth) headers["Authorization"] = auth;

  const upstream = await fetch(
    `${BACKEND_API_URL}/api/v1/${path}${request.nextUrl.search}`,
    { headers, signal: request.signal },
  );
  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

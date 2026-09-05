import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND_API_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

// GET-only 白名单代理：plans / user/profile / history*
// （POST /api/analyze 由静态路由处理，优先级高于本 catch-all）
const ALLOWED_PREFIXES = ["plans", "user/profile", "history"];

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } },
) {
  const path = params.path.join("/");
  // 拒绝点段与编码斜杠绕过：%2F 会被 Next 解码进参数，防止 .. 越出白名单前缀
  const badSeg = path.split("/").some((seg) => seg === "." || seg === ".." || seg === "");
  const allowed = !badSeg && ALLOWED_PREFIXES.some(
    (p) => path === p || path.startsWith(`${p}/`),
  );
  if (!allowed) {
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

// GET 白名单代理的路径校验：只放行白名单前缀，拒绝点段与反斜杠
// （WHATWG URL 会把反斜杠归一化为 /，从而绕过前缀检查）
const ALLOWED_PREFIXES = ["plans", "user/profile", "history"];

export function validateProxyPath(segments: string[]): string | null {
  if (segments.length === 0) return null;
  const bad = segments.some(
    (seg) => seg === "" || seg === "." || seg === ".." || seg.includes("\\"),
  );
  if (bad) return null;
  const path = segments.join("/");
  const allowed = ALLOWED_PREFIXES.some(
    (p) => path === p || path.startsWith(`${p}/`),
  );
  return allowed ? path : null;
}

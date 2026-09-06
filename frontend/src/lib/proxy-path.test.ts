import { describe, expect, it } from "vitest";

import { validateProxyPath } from "./proxy-path";

describe("validateProxyPath", () => {
  it("放行白名单内的精确路径与子路径", () => {
    expect(validateProxyPath(["plans"])).toBe("plans");
    expect(validateProxyPath(["user", "profile"])).toBe("user/profile");
    expect(validateProxyPath(["history"])).toBe("history");
    expect(validateProxyPath(["history", "123"])).toBe("history/123");
  });

  it("拒绝空路径与空分段", () => {
    expect(validateProxyPath([])).toBeNull();
    expect(validateProxyPath([""])).toBeNull();
    expect(validateProxyPath(["plans", ""])).toBeNull();
  });

  it("拒绝点段穿越", () => {
    expect(validateProxyPath(["..", "plans"])).toBeNull();
    expect(validateProxyPath(["history", "..", "plans"])).toBeNull();
    expect(validateProxyPath([".", "plans"])).toBeNull();
  });

  it("拒绝反斜杠绕过（WHATWG URL 会把 \\ 归一化为 /）", () => {
    expect(validateProxyPath(["history", "..\\plans"])).toBeNull();
    expect(validateProxyPath(["history\\..\\plans"])).toBeNull();
    expect(validateProxyPath(["plans\\..\\history"])).toBeNull();
  });

  it("拒绝白名单之外的前缀", () => {
    expect(validateProxyPath(["foo"])).toBeNull();
    expect(validateProxyPath(["user"])).toBeNull();
    expect(validateProxyPath(["plansx"])).toBeNull();
    expect(validateProxyPath(["history-plans"])).toBeNull();
  });
});

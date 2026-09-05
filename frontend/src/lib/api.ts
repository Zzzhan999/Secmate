import type { InputType } from "@/lib/input-classifier";
import { supabase } from "@/lib/supabase";

export interface StreamCallbacks {
  onMeta?: (inputType: InputType) => void;
  onDelta?: (content: string) => void;
  onDone?: (payload: { analysisId: number | null; tokensOut: number }) => void;
  onError?: (code: string, message: string) => void;
}

export class ApiError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

export interface UserProfile {
  email: string | null;
  plan: "free" | "pro";
  used_today: number;
  limit: number;
  remaining: number;
}

export interface HistoryItem {
  id: number;
  input_type: string;
  input_text: string;
  tokens_out: number;
  created_at: string;
}

export interface HistoryDetail {
  id: number;
  input_type: string;
  input_text: string;
  result_md: string;
  model: string | null;
  tokens_in: number;
  tokens_out: number;
  created_at: string;
}

export interface HistoryPage {
  items: HistoryItem[];
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface PricingPlan {
  id: string;
  name: string;
  price: number;
  price_unit: string;
  description: string;
  features: string[];
  highlighted: boolean;
  cta_text: string;
  coming_soon: boolean;
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  if (supabase) {
    const { data } = await supabase.auth.getSession();
    if (data.session) {
      headers["Authorization"] = `Bearer ${data.session.access_token}`;
    }
  }
  return headers;
}

async function fetchJson<T>(path: string): Promise<T> {
  const headers = await getAuthHeaders();
  const resp = await fetch(path, { headers });
  if (resp.status === 401) {
    // 登录已过期：清除本地会话，由页面跳转 /login
    await supabase?.auth.signOut();
    throw new ApiError("invalid_token", "登录已过期，请重新登录。");
  }
  if (!resp.ok) {
    let code = "unknown";
    let message = `请求失败（HTTP ${resp.status}）`;
    try {
      const body = await resp.json();
      const detail = body.detail ?? body;
      code = detail.code ?? code;
      message = detail.message ?? message;
    } catch {
      // 非 JSON 错误体，保留默认文案
    }
    throw new ApiError(code, message);
  }
  return (await resp.json()) as T;
}

export function fetchProfile(): Promise<UserProfile> {
  return fetchJson<UserProfile>("/api/user/profile");
}

export function fetchPlans(): Promise<{ plans: PricingPlan[] }> {
  return fetchJson<{ plans: PricingPlan[] }>("/api/plans");
}

export function fetchHistory(page: number, pageSize = 10): Promise<HistoryPage> {
  return fetchJson<HistoryPage>(`/api/history?page=${page}&page_size=${pageSize}`);
}

export function fetchHistoryDetail(id: number): Promise<HistoryDetail> {
  return fetchJson<HistoryDetail>(`/api/history/${id}`);
}

export function notifyQuotaRefresh() {
  window.dispatchEvent(new Event("secmate:quota-refresh"));
}

export async function streamAnalysis(
  inputText: string,
  inputType: InputType | null,
  cb: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const headers = await getAuthHeaders();
  const resp = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ input_text: inputText, input_type: inputType }),
    signal,
  });

  if (!resp.ok) {
    let code = "unknown";
    let message = `请求失败（HTTP ${resp.status}）`;
    try {
      const body = await resp.json();
      const detail = body.detail ?? body;
      code = detail.code ?? code;
      message = detail.message ?? message;
    } catch {
      // 非 JSON 错误体，保留默认文案
    }
    throw new ApiError(code, message);
  }

  if (!resp.body) {
    throw new ApiError("stream_error", "当前浏览器不支持流式响应");
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (!data) continue;
      let payload: Record<string, unknown>;
      try {
        payload = JSON.parse(data);
      } catch {
        continue;
      }
      if (event === "meta") cb.onMeta?.(payload.input_type as InputType);
      else if (event === "delta") cb.onDelta?.(String(payload.content ?? ""));
      else if (event === "done") cb.onDone?.(payload as { analysisId: number | null; tokensOut: number });
      else if (event === "error") cb.onError?.(String(payload.code ?? "unknown"), String(payload.message ?? "未知错误"));
    }
  }
}

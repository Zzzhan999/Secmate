import type { InputType } from "@/lib/input-classifier";

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

export async function streamAnalysis(
  inputText: string,
  inputType: InputType | null,
  cb: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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

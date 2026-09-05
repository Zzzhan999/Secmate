"use client";

import { AlertTriangle, ShieldAlert } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useCallback, useRef, useState } from "react";

import { AnalysisInput } from "@/components/analysis-input";
import { AnalysisResult } from "@/components/analysis-result";
import { SiteHeader } from "@/components/site-header";
import { UpgradeCard } from "@/components/upgrade-card";
import { Button } from "@/components/ui/button";
import { ApiError, notifyQuotaRefresh, streamAnalysis } from "@/lib/api";
import { isInputType, type InputType } from "@/lib/input-classifier";

type Status = "idle" | "streaming" | "done" | "error";

export function AnalyzeClient() {
  const params = useSearchParams();
  const typeParam = params.get("type");
  const [detectedType, setDetectedType] = useState<InputType | null>(
    isInputType(typeParam) ? typeParam : null,
  );
  const [result, setResult] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [quotaExceeded, setQuotaExceeded] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const handleAnalyze = useCallback(
    async (input: string) => {
      setQuotaExceeded(false);
      setResult("");
      setError(null);
      setStatus("streaming");
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await streamAnalysis(
          input,
          detectedType,
          {
            onMeta: (t) => setDetectedType(t),
            onDelta: (c) => setResult((prev) => prev + c),
            onDone: () => {
              setStatus("done");
              notifyQuotaRefresh();
            },
            onError: (_code, message) => {
              setError(message);
              setStatus("error");
            },
          },
          controller.signal,
        );
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          if (err instanceof ApiError && err.code === "quota_exceeded") {
            setQuotaExceeded(true);
            setStatus("idle");
          } else {
            setError(err instanceof ApiError ? err.message : "网络错误，请稍后重试");
            setStatus("error");
          }
        }
      }
    },
    [detectedType],
  );

  const handleStop = () => {
    abortRef.current?.abort();
    setStatus("done");
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI 安全分析</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            粘贴报错、HTTP 报文、代码或 CTF 题目，获取七段式学习讲解（流式输出）。
          </p>
        </div>
        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            <ShieldAlert className="mt-0.5 size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
        {quotaExceeded && <UpgradeCard />}
        <AnalysisInput
          onAnalyze={handleAnalyze}
          streaming={status === "streaming"}
          initialText={params.get("text") ?? ""}
        />
        {(status === "streaming" || status === "done" || result) && (
          <AnalysisResult content={result} streaming={status === "streaming"} />
        )}
        {status === "streaming" && (
          <div className="flex justify-center">
            <Button variant="outline" size="sm" onClick={handleStop}>
              <AlertTriangle />
              停止生成
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}

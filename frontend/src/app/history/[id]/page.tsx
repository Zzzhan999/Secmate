"use client";

import { Check, Copy } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Markdown } from "@/components/markdown";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { ApiError, fetchHistoryDetail, type HistoryDetail } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { INPUT_TYPE_LABELS, type InputType } from "@/lib/input-classifier";

export default function HistoryDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { session, loading } = useAuth();
  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!loading && !session) {
      router.replace("/login");
    }
  }, [loading, session, router]);

  useEffect(() => {
    if (!session || !params.id) return;
    let cancelled = false;
    fetchHistoryDetail(Number(params.id))
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((e: Error) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.code === "invalid_token") {
          router.replace("/login");
        } else {
          setError(e.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [session, params.id, router]);

  async function copyAll() {
    if (!detail) return;
    try {
      await navigator.clipboard.writeText(detail.result_md);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 剪贴板不可用时静默失败
    }
  }

  if (loading || !session) {
    return (
      <div className="min-h-screen bg-background text-foreground">
        <SiteHeader />
        <main className="mx-auto max-w-4xl px-4 py-16 text-center text-sm text-muted-foreground">
          加载中…
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-4xl space-y-4 px-4 py-8">
        {error && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
        {detail && (
          <>
            <div className="rounded-xl border border-border bg-card/60 p-5">
              <div className="flex items-center justify-between">
                <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                  {INPUT_TYPE_LABELS[detail.input_type as InputType] ?? detail.input_type}
                </span>
                <Button variant="outline" size="sm" onClick={copyAll}>
                  {copied ? <Check className="text-emerald-500" /> : <Copy />}
                  {copied ? "已复制" : "复制全文"}
                </Button>
              </div>
              <h2 className="mt-3 text-sm font-medium text-muted-foreground">
                原始输入
              </h2>
              <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-lg border border-border bg-background p-3 font-mono text-xs leading-relaxed">
                {detail.input_text}
              </pre>
            </div>
            <div className="rounded-xl border border-border bg-card/60 p-5">
              <h2 className="mb-4 border-b border-border pb-3 text-sm font-medium">
                分析结果
              </h2>
              {detail.result_md ? (
                <Markdown content={detail.result_md} />
              ) : (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  该记录没有结果内容（可能生成中断）。
                </p>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

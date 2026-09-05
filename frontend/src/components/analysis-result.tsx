"use client";

import { Check, Copy, Download } from "lucide-react";
import { useState } from "react";

import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";

const DISCLAIMER = "以上内容仅供授权环境下的学习与防御研究使用。";

export function AnalysisResult({ content, streaming }: { content: string; streaming: boolean }) {
  const [copied, setCopied] = useState(false);

  async function copyAll() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 剪贴板 API 不可用（如非 HTTPS）时静默失败
    }
  }

  function exportMd() {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `secmate-analysis-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="rounded-xl border border-border bg-card/60 p-5">
      <div className="mb-4 flex items-center justify-between gap-2 border-b border-border pb-3">
        <span className="text-sm font-medium">分析结果</span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={copyAll} disabled={!content}>
            {copied ? <Check className="text-emerald-500" /> : <Copy />}
            {copied ? "已复制" : "复制全文"}
          </Button>
          <Button variant="outline" size="sm" onClick={exportMd} disabled={!content}>
            <Download />
            导出 Markdown
          </Button>
        </div>
      </div>
      {streaming && !content && (
        <div className="space-y-3 py-2">
          <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
          <div className="h-3 w-full animate-pulse rounded bg-muted" />
          <div className="h-3 w-5/6 animate-pulse rounded bg-muted" />
          <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
        </div>
      )}
      {content ? (
        <Markdown content={content} />
      ) : (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {streaming ? "正在生成…" : "分析结果将在这里流式呈现"}
        </p>
      )}
      {content && !streaming && (
        <p className="mt-6 border-t border-border pt-3 text-xs text-muted-foreground">{DISCLAIMER}</p>
      )}
    </div>
  );
}

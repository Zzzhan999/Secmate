"use client";

import { Loader2, Send } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { EXAMPLES } from "@/lib/examples";
import { classifyInput, INPUT_TYPE_LABELS } from "@/lib/input-classifier";

const MAX_LENGTH = 8000;

export function AnalysisInput({
  onAnalyze,
  streaming,
  initialText = "",
}: {
  onAnalyze: (text: string) => void;
  streaming: boolean;
  initialText?: string;
}) {
  const [text, setText] = useState(initialText);
  const detected = classifyInput(text);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>粘贴你要分析的内容（报错 / 报文 / 代码 / 命令 / 题目均可）</span>
        <span className={text.length > MAX_LENGTH * 0.95 ? "text-destructive" : ""}>
          {text.length.toLocaleString()} / {MAX_LENGTH.toLocaleString()}
        </span>
      </div>
      <textarea
        value={text}
        maxLength={MAX_LENGTH}
        onChange={(e) => setText(e.target.value)}
        placeholder={'例如粘贴一段报错：\n\nTraceback (most recent call last):\n  File "app.py", line 10, in <module> ...'}
        className="h-56 w-full resize-y rounded-lg border border-input bg-card/60 p-4 font-mono text-sm outline-none transition-colors placeholder:text-muted-foreground/60 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-muted-foreground">自动识别：</span>
          <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
            {INPUT_TYPE_LABELS[detected]}
          </span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              type="button"
              disabled={streaming}
              onClick={() => setText(ex.text)}
              className="rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground transition-colors hover:border-emerald-500/40 hover:text-foreground disabled:opacity-50"
            >
              示例：{ex.label}
            </button>
          ))}
        </div>
        <Button size="lg" disabled={streaming || text.trim().length === 0} onClick={() => onAnalyze(text)}>
          {streaming ? <Loader2 className="animate-spin" /> : <Send />}
          {streaming ? "分析中…" : "开始分析"}
        </Button>
      </div>
    </div>
  );
}

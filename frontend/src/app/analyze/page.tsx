import type { Metadata } from "next";
import { Suspense } from "react";

import { AnalyzeClient } from "@/components/analyze-client";

export const metadata: Metadata = {
  title: "AI 安全分析 - SecMate",
  description: "粘贴报错、HTTP 报文、代码或 CTF 题目，获取七段式流式学习讲解。",
};

export default function AnalyzePage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-muted-foreground">加载中…</div>}>
      <AnalyzeClient />
    </Suspense>
  );
}

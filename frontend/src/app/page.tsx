import Link from "next/link";
import {
  ArrowRight,
  Braces,
  Bug,
  FileCode2,
  Flag,
  Globe,
  ShieldCheck,
  Terminal,
} from "lucide-react";

import { SiteHeader } from "@/components/site-header";
import { buttonVariants } from "@/components/ui/button";
import { EXAMPLES } from "@/lib/examples";

const FEATURES = [
  { icon: Globe, title: "HTTP 报文分析", desc: "逐行解读请求行、请求头与报文体的结构语义" },
  { icon: Bug, title: "报错信息诊断", desc: "从报错定位根因，讲解背后的信息泄露风险" },
  { icon: Braces, title: "代码安全分析", desc: "发现代码风险点，给出防御写法示例" },
  { icon: Flag, title: "CTF 思路引导", desc: "给方向、讲原理、提示关键点，不直接给答案" },
  { icon: Terminal, title: "Linux 命令解读", desc: "命令意图、参数含义与安全注意点" },
  { icon: FileCode2, title: "网络协议讲解", desc: "TCP / DNS / TLS 等协议原理与常见缺陷" },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:48px_48px] opacity-20 [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,black,transparent)]"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -top-32 left-1/2 h-72 w-[36rem] -translate-x-1/2 rounded-full bg-emerald-500/20 blur-3xl"
        />
        <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-24 text-center sm:pt-32">
          <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
            <ShieldCheck className="size-3.5" />
            AI Powered Cyber Security Learning Assistant
          </div>
          <h1 className="text-5xl font-bold tracking-tight sm:text-7xl">SecMate</h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
            把看不懂的报错、请求、命令、CTF 题目，变成讲得清原理、给得出方向、指得明练习环境的学习材料。
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <Link href="/analyze" className={buttonVariants({ size: "lg", className: "h-11 px-6 text-base" })}>
              开始分析
              <ArrowRight />
            </Link>
            <Link
              href="#features"
              className={buttonVariants({ variant: "outline", size: "lg", className: "h-11 px-6 text-base" })}
            >
              了解特性
            </Link>
          </div>
          <p className="mt-6 text-xs text-muted-foreground">
            每日免费体验 · 无需注册 · 仅支持授权环境（靶场）下的学习与防御研究
          </p>
        </div>
      </section>

      {/* 特性区 */}
      <section id="features" className="mx-auto max-w-6xl px-4 py-16">
        <h2 className="text-center text-2xl font-bold tracking-tight">六类输入，一种解法</h2>
        <p className="mx-auto mt-2 max-w-xl text-center text-sm text-muted-foreground">
          自动识别输入类型，按「七段式」结构化讲解：问题分析 → 原理解释 → 学习方向 → 排查思路 → 修复建议 → 知识点 → 练习环境
        </p>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="rounded-xl border border-border bg-card/60 p-5 transition-colors hover:border-emerald-500/40"
            >
              <div className="flex size-9 items-center justify-center rounded-lg border border-border text-emerald-500">
                <f.icon className="size-4.5" />
              </div>
              <h3 className="mt-3 font-medium">{f.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 示例区 */}
      <section className="mx-auto max-w-6xl px-4 pb-20">
        <h2 className="text-center text-2xl font-bold tracking-tight">先看个例子</h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {EXAMPLES.map((ex) => (
            <Link
              key={ex.label}
              href={`/analyze?type=${ex.type}&text=${encodeURIComponent(ex.text)}`}
              className="group rounded-xl border border-border bg-card/60 p-5 transition-colors hover:border-emerald-500/40"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">{ex.label}</span>
                <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </div>
              <pre className="mt-3 line-clamp-4 overflow-hidden whitespace-pre-wrap break-all font-mono text-xs leading-relaxed text-muted-foreground">
                {ex.text}
              </pre>
            </Link>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-4 py-8 text-center text-xs text-muted-foreground">
          <p>SecMate 仅支持授权环境（靶场）下的学习与防御研究，所有分析结果仅供学习使用。</p>
          <p>© 2026 SecMate · MIT License</p>
        </div>
      </footer>
    </div>
  );
}

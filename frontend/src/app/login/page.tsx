"use client";

import { LogIn } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { supabase } from "@/lib/supabase";

type Mode = "signin" | "signup";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!supabase) {
      setError("登录服务未配置，请联系管理员。");
      return;
    }
    setSubmitting(true);
    setError(null);
    const { error: err } =
      mode === "signin"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password });
    setSubmitting(false);
    if (err) {
      const msg = err.message.toLowerCase();
      if (msg.includes("already registered")) {
        setError("该邮箱已注册，请直接登录。");
      } else if (msg.includes("invalid login credentials")) {
        setError("邮箱或密码错误。");
      } else {
        setError(err.message);
      }
      return;
    }
    router.push("/analyze");
  }

  async function githubLogin() {
    if (!supabase) {
      setError("登录服务未配置，请联系管理员。");
      return;
    }
    const { error: err } = await supabase.auth.signInWithOAuth({
      provider: "github",
      options: { redirectTo: `${window.location.origin}/analyze` },
    });
    if (err) setError("GitHub 登录方式未配置，请使用邮箱登录。");
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-md px-4 py-16">
        <div className="rounded-xl border border-border bg-card/60 p-6">
          <h1 className="text-xl font-bold">
            {mode === "signin" ? "登录 SecMate" : "注册 SecMate"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {mode === "signin"
              ? "登录后解锁每日 5 次个人配额与历史记录"
              : "注册即可获得每日 5 次免费分析额度"}
          </p>
          {error && (
            <div className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <form onSubmit={submit} className="mt-4 space-y-3">
            <label className="block">
              <span className="text-sm font-medium">邮箱</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                placeholder="you@example.com"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium">密码</span>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                placeholder="至少 8 位"
              />
            </label>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "请稍候…" : mode === "signin" ? "登录" : "注册"}
            </Button>
          </form>
          <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground">
            <div className="h-px flex-1 bg-border" />
            或
            <div className="h-px flex-1 bg-border" />
          </div>
          <Button variant="outline" className="w-full" onClick={githubLogin}>
            <LogIn />
            使用 GitHub 登录
          </Button>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            {mode === "signin" ? "还没有账号？" : "已有账号？"}
            <button
              className="ml-1 text-primary hover:underline"
              onClick={() => {
                setMode(mode === "signin" ? "signup" : "signin");
                setError(null);
              }}
            >
              {mode === "signin" ? "立即注册" : "去登录"}
            </button>
          </p>
        </div>
      </main>
    </div>
  );
}

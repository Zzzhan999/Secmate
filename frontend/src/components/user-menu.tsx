"use client";

import Link from "next/link";
import { CreditCard, History, LogOut } from "lucide-react";

import { QuotaBadge } from "@/components/quota-badge";
import { buttonVariants } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { supabase } from "@/lib/supabase";

export function UserMenu() {
  const { session, loading } = useAuth();

  if (loading) {
    return <div className="h-8 w-20 animate-pulse rounded-lg bg-muted" />;
  }
  if (!session) {
    return (
      <Link href="/login" className={buttonVariants({ variant: "outline", size: "sm" })}>
        登录
      </Link>
    );
  }
  const email = session.user.email ?? "已登录";

  async function signOut() {
    await supabase?.auth.signOut();
  }

  return (
    <div className="group relative">
      <button className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-1.5 text-sm transition-colors hover:bg-muted">
        <span className="max-w-40 truncate">{email}</span>
        <QuotaBadge />
      </button>
      <div className="invisible absolute right-0 top-full z-50 mt-1 w-44 rounded-lg border border-border bg-popover p-1 opacity-0 shadow-md transition-all group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100">
        <Link
          href="/history"
          className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm transition-colors hover:bg-muted"
        >
          <History className="size-4" />
          分析历史
        </Link>
        <Link
          href="/pricing"
          className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm transition-colors hover:bg-muted"
        >
          <CreditCard className="size-4" />
          定价与升级
        </Link>
        <button
          onClick={signOut}
          className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-sm transition-colors hover:bg-muted"
        >
          <LogOut className="size-4" />
          退出登录
        </button>
      </div>
    </div>
  );
}

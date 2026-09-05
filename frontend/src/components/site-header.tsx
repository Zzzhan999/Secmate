import Link from "next/link";
import { ShieldCheck } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/user-menu";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <ShieldCheck className="size-5 text-emerald-500" />
          <span>SecMate</span>
        </Link>
        <nav className="flex items-center gap-3">
          <Link
            href="/analyze"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            开始分析
          </Link>
          <UserMenu />
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}

import Link from "next/link";
import { Crown } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";

export function UpgradeCard() {
  return (
    <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/5 p-6 text-center">
      <Crown className="mx-auto size-8 text-emerald-500" />
      <h3 className="mt-3 text-lg font-semibold">今日免费额度已用完</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Free 方案每日 5 次分析。升级 Pro 解锁每日 200 次与完整历史记录。
      </p>
      <Link href="/pricing" className={buttonVariants({ className: "mt-4" })}>
        查看 Pro 定价
      </Link>
    </div>
  );
}

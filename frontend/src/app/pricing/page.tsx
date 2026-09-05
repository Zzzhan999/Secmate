"use client";

import { useEffect, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { fetchPlans, type PricingPlan } from "@/lib/api";

export default function PricingPage() {
  const [plans, setPlans] = useState<PricingPlan[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchPlans()
      .then((data) => {
        if (!cancelled) setPlans(data.plans);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-4 py-12">
        <h1 className="text-center text-3xl font-bold tracking-tight">
          选择适合你的方案
        </h1>
        <p className="mx-auto mt-2 max-w-xl text-center text-sm text-muted-foreground">
          SecMate 定价（支付功能即将上线，当前仅支持 Free 方案）
        </p>
        {error && (
          <p className="mt-6 text-center text-sm text-destructive">{error}</p>
        )}
        {plans ? (
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {plans.map((plan) => (
              <div
                key={plan.id}
                className={`flex flex-col rounded-xl border p-5 ${
                  plan.highlighted
                    ? "border-emerald-500/50 bg-emerald-500/5"
                    : "border-border bg-card/60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold">{plan.name}</h2>
                  {plan.highlighted && (
                    <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-600 dark:text-emerald-400">
                      推荐
                    </span>
                  )}
                </div>
                <div className="mt-3">
                  <span className="text-3xl font-bold">
                    {plan.price === 0 ? "¥0" : `¥${plan.price}`}
                  </span>
                  <span className="ml-1 text-sm text-muted-foreground">
                    {plan.price_unit}
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {plan.description}
                </p>
                <ul className="mt-4 flex-1 space-y-2 text-sm">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2">
                      <span className="mt-1.5 size-1 shrink-0 rounded-full bg-emerald-500" />
                      {f}
                    </li>
                  ))}
                </ul>
                <Button
                  variant={plan.highlighted ? "default" : "outline"}
                  className="mt-5 w-full"
                  disabled={plan.coming_soon}
                >
                  {plan.cta_text}
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-10 text-center text-sm text-muted-foreground">
            正在加载方案…
          </p>
        )}
      </main>
    </div>
  );
}

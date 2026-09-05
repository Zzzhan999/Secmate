"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { ApiError, fetchHistory, type HistoryItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { INPUT_TYPE_LABELS, type InputType } from "@/lib/input-classifier";

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", { hour12: false });
}

function typeLabel(t: string): string {
  return INPUT_TYPE_LABELS[t as InputType] ?? t;
}

export default function HistoryPage() {
  const router = useRouter();
  const { session, loading } = useAuth();
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !session) {
      router.replace("/login");
    }
  }, [loading, session, router]);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    fetchHistory(1)
      .then((data) => {
        if (cancelled) return;
        setItems(data.items);
        setHasMore(data.has_more);
        setPage(1);
      })
      .catch((e: Error) => {
        if (!cancelled) {
          if (e instanceof ApiError && e.code === "invalid_token") {
            router.replace("/login");
          } else {
            setError(e.message);
          }
        }
      });
    return () => {
      cancelled = true;
    };
  }, [session, router]);

  async function loadMore() {
    const next = page + 1;
    try {
      const data = await fetchHistory(next);
      setItems((prev) => [...(prev ?? []), ...data.items]);
      setHasMore(data.has_more);
      setPage(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
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
        <div>
          <h1 className="text-2xl font-bold tracking-tight">分析历史</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            你的全部分析记录（仅本人可见）
          </p>
        </div>
        {error && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
        {items === null ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            正在加载…
          </p>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-border bg-card/60 p-10 text-center">
            <p className="text-sm text-muted-foreground">
              还没有分析记录，去
              <Link href="/analyze" className="mx-1 text-primary hover:underline">
                开始分析
              </Link>
              吧。
            </p>
          </div>
        ) : (
          <>
            <ul className="space-y-3">
              {items.map((item) => (
                <li key={item.id}>
                  <Link
                    href={`/history/${item.id}`}
                    className="block rounded-xl border border-border bg-card/60 p-4 transition-colors hover:border-emerald-500/40"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                        {typeLabel(item.input_type)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {formatTime(item.created_at)}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 break-all text-sm text-foreground/80">
                      {item.input_text || "（空输入）"}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
            {hasMore && (
              <div className="flex justify-center">
                <Button variant="outline" size="sm" onClick={loadMore}>
                  加载更多
                </Button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

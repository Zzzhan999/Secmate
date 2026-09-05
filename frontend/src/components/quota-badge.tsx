"use client";

import { useEffect, useState } from "react";

import { fetchProfile, type UserProfile } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function QuotaBadge() {
  const { session } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);

  useEffect(() => {
    if (!session) {
      setProfile(null);
      return;
    }
    let cancelled = false;
    async function load() {
      try {
        const p = await fetchProfile();
        if (!cancelled) setProfile(p);
      } catch {
        // 401/503 等：徽章静默不显示（401 已由 fetchJson 触发全局登出）
      }
    }
    load();
    window.addEventListener("secmate:quota-refresh", load);
    return () => {
      cancelled = true;
      window.removeEventListener("secmate:quota-refresh", load);
    };
  }, [session]);

  if (!session || !profile) return null;
  return (
    <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
      今日剩余 {profile.remaining} 次
    </span>
  );
}

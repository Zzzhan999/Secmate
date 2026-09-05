import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// 未配置时为 null：构建/预览环境可正常渲染，登录功能提示「未配置」
const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const supabase: SupabaseClient | null =
  url && anonKey ? createClient(url, anonKey) : null;

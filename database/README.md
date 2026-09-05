# database/ — Supabase PostgreSQL

本目录存放 SecMate 的数据库脚本。数据库使用 Supabase 云 PostgreSQL（免费额度即可支撑 MVP）。

## 执行步骤

1. 在 [supabase.com](https://supabase.com) 创建项目（记得开启 Auth）；
2. 打开 **SQL Editor**；
3. 先执行 `schema.sql`（建表 + 触发器 + RLS）；
4. 再执行 `seed_prompts.sql`（6 个场景的系统提示词种子数据）。

## 表清单

| 表 | 用途 | 启用阶段 |
|----|------|----------|
| `profiles` | 用户档案（1:1 关联 `auth.users`，注册自动创建） | 阶段4 |
| `analyses` | 分析记录（支持匿名，`user_id` 可空） | 阶段3 |
| `daily_usage` | 每日配额计数（联合主键原子计数） | 阶段4 |
| `subscriptions` | 订阅状态 | 阶段4 |
| `orders` | 订单（支付接口预留） | 阶段4 |
| `prompts` | Prompt 模板（后台可管理） | 阶段5 |
| `shared_links` | 分享链接 | 阶段5 |

## 说明

- 所有表启用了 RLS（默认拒绝访问），后端使用 service_role key 读写，不受 RLS 限制；阶段4 再为客户端直连接口细化策略。
- 本地开发也可用 `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16` 起一个裸 PostgreSQL 调试 SQL，但 `auth.users` 依赖 Supabase，完整验证请在 Supabase 项目中进行。

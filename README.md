# SecMate — AI Powered Cyber Security Learning Assistant

AI 网络安全学习助手：把看不懂的报错、请求、命令、CTF 题目，变成讲得清原理、给得出方向、指得明练习环境的学习材料。

> **教育与防御视角**：所有分析仅用于授权环境（靶场）学习，不针对真实目标。

## 目录结构

```
SecMate/
├── frontend/    # Next.js 14 + TypeScript + Tailwind + shadcn（部署 Vercel）
├── backend/     # Python FastAPI + AI 适配层（部署 DigitalOcean）
├── database/    # Supabase PostgreSQL schema 与种子数据
└── docs/        # 设计文档与实施计划
```

## 快速开始

### 前端

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev          # http://localhost:3000
```

### 后端

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements-dev.txt
cp .env.example .env            # 填入 AI_API_KEY（DeepSeek 等）
uvicorn app.main:app --reload   # http://localhost:8000/api/v1/health
```

> 若 8000 端口被占用：`uvicorn app.main:app --reload --port 8001`，并在 `frontend/.env.local` 中设置 `BACKEND_API_URL=http://localhost:8001`。

### 数据库

1. 创建 [Supabase](https://supabase.com) 项目（免费额度即可）；
2. 打开 SQL Editor，依次执行 `database/schema.sql`、`database/seed_prompts.sql`。

## 文档

- 设计与需求（PRD/架构/商业化/路线图）：`docs/superpowers/specs/2026-09-05-secmate-design.md`
- 各阶段实施计划：`docs/superpowers/plans/`
- 部署手册（Supabase/DO/Caddy/Vercel）：`docs/deploy.md`

## 当前进度

| 阶段 | 内容 | 状态 |
|------|------|------|
| 1 | 需求分析 | ✅ 完成 |
| 2 | 项目结构 | ✅ 完成 |
| 3 | MVP（首页/分析页/AI 分析 API） | ✅ 完成（2026-09-05） |
| 4 | 商业化（用户/会员/支付预留） | ✅ 完成（2026-09-05） |
| 5 | 优化（历史/收藏/分享/SEO/统计） | 未开始 |

## 阶段4（商业化）已上线

- 邮箱注册/登录（Supabase Auth，JWT 由后端本地验签），GitHub OAuth 按钮预留（需在 Supabase 配置 GitHub provider）
- Free 5 次/天个人配额（Postgres RPC 原子扣减），Pro 200 次/天上限代码路径就绪
- 分析历史（列表 + 详情，仅本人可见）
- 定价页四档方案（数据来自 `GET /api/v1/plans`），支付接口预留，升级按钮「即将上线」
- 匿名分析保持可用（IP 限流兜底，Supabase 未配置时全链路降级）

**上线前需在 Supabase 完成：** SQL Editor 执行 `database/schema.sql`；Authentication → Email → 关闭 Confirm email。

**新环境变量：** 后端 `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_JWT_SECRET`；前端 `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`。

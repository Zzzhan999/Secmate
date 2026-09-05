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
| 4 | 商业化（用户/会员/支付预留） | ⏳ 下一阶段 |
| 5 | 优化（历史/收藏/分享/SEO/统计） | 未开始 |

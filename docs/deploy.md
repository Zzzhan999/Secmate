# SecMate 部署手册（M8）

> 上线需要以下账户：Vercel（前端）、DigitalOcean（后端）、Supabase（数据库）。
> 全程费用 ≈ ¥50/月：Vercel Hobby ¥0 + DO 最低配 ≈¥43/月 + Supabase Free ¥0。

## 1. Supabase（数据库）

1. 创建项目（Free 档）→ SQL Editor 依次执行 `database/schema.sql`、`database/seed_prompts.sql`
2. Project Settings → API 记下 `Project URL` 与 `service_role` key（**绝不进前端代码/仓库**）
3. 阶段3 匿名分析无用户依赖，此步完成即满足 M7 落库条件

## 2. DigitalOcean（后端）

1. 创建 Droplet：Ubuntu 24.04，最低配（1 vCPU / 1GB，≈¥43/月），SSH 登录
2. 安装 Docker：

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && exit
```

3. 拉代码并配置：

```bash
git clone <你的仓库地址> secmate && cd secmate/backend
cp .env.example .env
vim .env   # 填 DEEPSEEK_API_KEY、SUPABASE_URL、SUPABASE_SERVICE_ROLE_KEY、CORS 来源
```

4. 启动：

```bash
docker compose up -d --build
curl http://127.0.0.1:8000/api/v1/health   # 期望 {"status":"ok",...}
```

## 3. Caddy（HTTPS 反代）

1. 安装 Caddy：

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

2. 编辑 `/etc/caddy/Caddyfile`：

```
api.your-domain.com {
    reverse_proxy 127.0.0.1:8000
}
```

3. `sudo systemctl reload caddy` — HTTPS 证书自动签发与续期。

## 4. Vercel（前端）

1. GitHub 导入仓库（Root Directory 设为 `frontend`），Framework 自动识别 Next.js
2. 环境变量：`BACKEND_API_URL=https://api.your-domain.com`
3. Deploy 后验证首页；域名 A 记录解析到 Vercel（或使用 *.vercel.app）

## 5. 上线检查清单

- [ ] `GET /api/v1/health` 返回 ok（后端）
- [ ] 前端首页/分析页 HTTPS 可访问
- [ ] 真实分析：粘贴一段报错，收到流式七段式输出（首 token < 2s）
- [ ] 安全护栏：真实目标攻击语句被 400 拒绝；敏感信息被 400 拒绝
- [ ] 快速连点「开始分析」触发 429
- [ ] Supabase `analyses` 表出现新记录
- [ ] 后端日志不含用户输入内容

# SecMate 部署手册（Vercel + Render 免费档）

> 目标架构：前端 Next.js → Vercel（免费 Hobby）｜后端 FastAPI → Render（免费档）｜数据库 Supabase（已有）｜域名绑定 Vercel。
> 本次部署目标：前端 `https://betterapi.tech`（Vercel），后端 `https://<服务名>.onrender.com`（Render）。
> 全程费用 ≈ ¥0/月（不含你已有的域名与 AI API 消耗）。
> 备选：若日后要自管服务器，本仓库保留 `backend/docker-compose.yml` + Caddy 反代方案（见文末附录），可平滑迁移。

## 0. 一次性前置

### 0.1 轮换 Supabase service_role 密钥（务必先做）

`sb_secret_*` 旧密钥曾在开发期进入过 git 历史（已通过历史重写清除痕迹），**但泄露过的密钥必须轮换才能作废**：

1. Supabase Dashboard → 你的项目 → Project Settings → API Keys
2. 在 `service_role` 行点 Revoke → 复制新生成的 key
3. 若顺手在下方 JWT Settings 重置了 JWT Secret，也请同步更新（见 1.2 环境变量表），且所有已登录用户需重新登录

### 0.2 GitHub 建仓并推送

Vercel 与 Render 都从 GitHub 导入，需要先把代码推上去（推荐 private 起步，练手结束想开源再改可见性）：

```bash
git remote add origin https://github.com/<你的账户>/<仓库名>.git
git push -u origin main
```

推送前会做一次全仓密钥扫描确认无泄漏（`.env` 已被 gitignore，不会进仓库）。

### 0.3 域名

绑到 Vercel 的域名**无需备案**（Vercel 服务在海外）。解析按第 3 节做即可。

## 1. 后端：Render（免费档）

1. 打开 https://dashboard.render.com → **New +** → **Web Service**
2. **Connect** 你的 GitHub 仓库（首次需授权 Render 读仓库）
3. 填写：
   - **Root Directory**: `backend`
   - **Runtime**: Docker（仓库已有 Dockerfile，监听 `$PORT`，兼容 Render 注入）
   - **Region**: Singapore（对国内延迟相对友好；或就近选 Oregon）
   - **Instance Type**: Free
4. 展开 **Environment Variables**，手动添加（值不含引号，`CORS_ORIGINS` 是 JSON 数组）：

   | 变量 | 值 |
   |---|---|
   | `ENVIRONMENT` | `production` |
   | `CORS_ORIGINS` | `["http://localhost:3000","https://betterapi.tech"]` |
   | `AI_PROVIDER` | `openai_compat` |
   | `AI_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4` |
   | `AI_API_KEY` | `<智谱 API Key>` |
   | `AI_MODEL` | `glm-4-flash` |
   | `RATE_LIMIT_PER_MINUTE` | `10` |
   | `SUPABASE_URL` | `https://<PROJECT_REF>.supabase.co` |
   | `SUPABASE_SERVICE_ROLE_KEY` | `<0.1 轮换后的新 key>` |
   | `SUPABASE_JWT_SECRET` | `<Dashboard → API Keys → JWT Settings>` |

   `PORT` 由 Render 自动注入，**不要**手动添加。所有值都不会进仓库。

5. **Create Web Service** → 等待 Build + Deploy（首次约 3-5 分钟，日志在侧边 **Logs** 可见）
6. 验证：打开 `https://<服务名>.onrender.com/api/v1/health`，应返回 `{"status":"ok", ...}`

> **免费档限制**：闲置 15 分钟进入休眠，下一个请求会触发冷启动（约 30-60 秒后才响应）。个人练手可接受；在意可后续升级 Starter 或迁自管服务器。

## 2. 前端：Vercel（免费 Hobby）

1. 打开 https://vercel.com → **Add New…** → **Project** → Import 同一个 GitHub 仓库
2. **Root Directory** 选 `frontend`（Framework Preset 会自动识别 Next.js，无需改）
3. **Environment Variables**（Production 与 Preview 都填）：

   | 变量 | 值 |
   |---|---|
   | `BACKEND_API_URL` | `https://<服务名>.onrender.com` |
   | `NEXT_PUBLIC_SUPABASE_URL` | `https://<PROJECT_REF>.supabase.co` |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `<publishable key>` |

   > `NEXT_PUBLIC_*` 会打进浏览器包，只允许放 publishable（匿名）凭据；service_role 绝不进前端。

4. **Deploy** → 得到 `https://<项目名>.vercel.app`，先在此地址完成第 4 节验收，再绑域名

## 3. 绑定域名（Vercel）

1. Vercel 项目 → **Settings** → **Domains** → 输入你的域名 → **Add**
2. 按 Vercel 提示去域名注册商后台加 DNS 记录（Vercel 会指明是 CNAME 还是 ALIAS、指向哪里）
3. 等待生效（几分钟到几小时），HTTPS 证书自动签发
4. 若此前 `CORS_ORIGINS` 里用了占位域名，回 Render → Environment → 改成正式域名 → **Manual Deploy**（或 Deploy 按钮）重新部署

## 4. 上线验收清单

部署完成后逐项勾：

- [ ] `https://<后端>.onrender.com/api/v1/health` 返回 ok（首次可能因冷启动等待）
- [ ] 首页/分析页 HTTPS 可访问，暗色模式正常
- [ ] 注册新用户 → 自动登录 → 配额徽章显示 5 次
- [ ] 完成一次真实分析：粘贴报错，收到流式七段式输出（冷启动后首 token 应 < 3s）
- [ ] 快速连点「开始分析」触发 429 或配额耗尽提示
- [ ] 安全护栏：提交真实目标攻击语句被拒绝；含手机号的输入被要求脱敏
- [ ] 历史列表出现刚才的分析；详情页内容完整
- [ ] Supabase 里检查落库：SQL Editor 执行
      `select input_text, result_md from analyses order by id desc limit 3;`
      确认**没有**任何真实手机号/邮箱/密钥原文（脱敏后应含 `[已脱敏:类别]` 占位）
- [ ] Render **Logs** 里搜索上述输入片段，确认日志不含用户输入内容
- [ ] 登录过期（清掉 localStorage 后访问 /history）会跳转 /login

## 5. 日常更新流程

```text
本地 git push main
  → Vercel：Git 集成自动构建部署前端
  → Render：免费档无自动部署，需进服务点 Manual Deploy（后续可用 Blueprint 加自动）
```

回滚：Vercel 在 Deployments 里选旧版本 Redeploy；Render 在 Events 里可 Rollback。

## 6. 常见问题

| 症状 | 原因与处理 |
|---|---|
| 前端能开但分析转圈后报错 | 浏览器 Network 看 `/api/analyze` 请求：若 502/网络错误，多半 `BACKEND_API_URL` 填错或后端在冷启动 |
| 分析接口报 CORS 错误 | `CORS_ORIGINS` 是 JSON 数组且包含当前访问来源（含 https 前缀），改后 Manual Deploy |
| 登录后立刻 401 | `SUPABASE_JWT_SECRET` 与 Dashboard 不一致（轮换过 JWT Secret 时必中此坑）；或会话是轮换前签发的，重新登录即可 |
| 历史为空 | 确认分析走的是**登录态**（配额徽章可见才算登录）；匿名分析只落库不显示 |
| Render 日志出现 `Supabase 未配置，跳过分析落库` | 环境变量没生效或键名拼错，检查 Service Environment 页面 |

## 附录：自管服务器方案（可选项）

原方案（DigitalOcean / 任意 Ubuntu 主机 + Docker + Caddy，约 ¥43/月）：

```bash
# 主机上
git clone <仓库> secmate && cd secmate/backend
cp .env.example .env && vim .env      # 填全部密钥与 CORS_ORIGINS（JSON 数组）
docker compose up -d --build          # Dockerfile 未设 $PORT 时回退 8000
```

Caddyfile 反代并自动签发 HTTPS：

```
api.你的域名.com {
    reverse_proxy 127.0.0.1:8000
}
```

前端仍走 Vercel 或迁移到同一台主机的静态托管均可；迁移时把 Render 的 10 个环境变量原样搬进 `.env` 即可，代码零改动。

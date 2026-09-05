# SecMate 阶段3 MVP 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 MVP 闭环：首页（M1）、分析页（M2）、流式分析 API（M3）、AI 适配层联调（M4）、安全护栏（M5）、IP 限流（M6）、匿名记录落库（M7），并输出部署文档（M8 代码侧准备）。

**Architecture:** FastAPI 新增 `POST /api/v1/analysis` SSE 流式接口：安全检测 → 限流 → 类型识别 → 内置提示词 → Provider 流式生成 → 落库。Next.js 侧通过 `/api/analyze` 代理路由透传 SSE，分析页用 fetch 流式读取并增量渲染 Markdown（react-markdown + rehype-highlight 代码高亮）。

**Tech Stack:** FastAPI + httpx；Next.js 14 App Router + Tailwind v4 + shadcn（base-nova）+ react-markdown + remark-gfm + rehype-highlight + next-themes；pytest；Supabase PostgREST（未配置时优雅跳过落库）。

---

## 范围说明

- **SSE 协议**：`event: meta`（input_type）→ 多个 `event: delta`（content）→ `event: done`（analysis_id/tokens_out）；异常时 `event: error`。限流/拒绝/非法输入返回普通 JSON 4xx。
- **输入类型**：后端 `classify()` 为唯一权威；前端同规则仅用于分析前的 UI 徽标预览。
- **落库**：未配置 Supabase 时跳过（本地无库可完整跑通）；配置后经 PostgREST + service_role 写入 `analyses`。
- **M8 部署**：本阶段产出部署文档与配置；真实上线需用户 Vercel/DigitalOcean/Supabase 账户，由用户配合完成（文档含逐步命令）。
- **真实 DeepSeek 联调**：需要用户提供 API Key（`backend/.env`）。无 Key 时以 MockTransport 单测 + 真实 401 错误路径做验证。

## 文件结构总览

**后端（新增）**
- `backend/app/schemas/analysis.py` — 分析请求模型
- `backend/app/services/tokens.py` — token 估算
- `backend/app/services/input_classifier.py` — 6 类输入识别
- `backend/app/services/safety.py` — 敏感信息检测 + 真实目标拒绝
- `backend/app/services/rate_limiter.py` — 内存滑动窗口限流
- `backend/app/services/recorder.py` — 分析记录落库（PostgREST）
- `backend/app/prompts/system_prompts.py` — 6 场景内置提示词（与 seed_prompts.sql 一致）
- `backend/app/api/routes/analysis.py` — SSE 分析路由
- `backend/tests/test_tokens.py`、`test_input_classifier.py`、`test_safety.py`、`test_rate_limiter.py`、`test_system_prompts.py`、`test_recorder.py`、`test_analysis_route.py`

**后端（修改）**
- `backend/app/core/config.py` — 增加 `rate_limit_per_minute`
- `backend/app/main.py` — 注册 analysis 路由
- `backend/.env.example` — 增加限流配置项

**前端（新增）**
- `frontend/src/lib/input-classifier.ts` — 类型识别 + 标签（与后端同规则）
- `frontend/src/lib/examples.ts` — 首页/分析页共用示例数据
- `frontend/src/lib/api.ts` — SSE 流式客户端
- `frontend/src/app/api/analyze/route.ts` — 后端代理路由
- `frontend/src/components/theme-provider.tsx`、`theme-toggle.tsx` — 暗色模式
- `frontend/src/components/site-header.tsx` — 顶部导航
- `frontend/src/components/markdown.tsx` — Markdown 渲染器
- `frontend/src/components/analysis-input.tsx` — 输入区
- `frontend/src/components/analysis-result.tsx` — 结果区（复制/导出）
- `frontend/src/components/analyze-client.tsx` — 分析页状态机

**前端（修改）**
- `frontend/package.json` — 新增 4 个依赖
- `frontend/src/app/layout.tsx` — ThemeProvider + suppressHydrationWarning
- `frontend/src/app/page.tsx` — 正式首页（M1）
- `frontend/src/app/analyze/page.tsx` — 分析页壳（Suspense）
- `frontend/src/app/globals.css` — highlight.js 主题 + markdown 样式
- `frontend/.env.local.example` — 补充端口说明

**文档（新增）**
- `docs/deploy.md` — Vercel + DigitalOcean + Supabase 部署手册

---

## Task 1: 后端输入分类器与 token 估算（TDD）

**Files:**
- Create: `backend/app/services/tokens.py`
- Create: `backend/app/services/input_classifier.py`
- Test: `backend/tests/test_tokens.py`
- Test: `backend/tests/test_input_classifier.py`

- [ ] **Step 1.1: 写失败测试**

创建 `backend/tests/test_tokens.py`：

```python
from app.services.tokens import estimate_tokens


def test_cjk_chars_count_as_one_token_each():
    assert estimate_tokens("你好") == 2


def test_latin_chars_grouped_by_four():
    assert estimate_tokens("hello world") == 3  # 11 字符 / 4 ≈ 2.75 → 3


def test_empty_text_returns_at_least_one():
    assert estimate_tokens("") == 1
```

创建 `backend/tests/test_input_classifier.py`：

```python
import pytest

from app.services.input_classifier import classify

CASES = [
    # (输入, 期望类型)
    ("POST /login HTTP/1.1\nHost: example.com", "http"),
    ("HTTP/1.1 500 Internal Server Error\nContent-Type: text/html", "http"),
    ("Traceback (most recent call last):\n  File \"app.py\", line 3, in <module>\n    x = 1/0\nZeroDivisionError: division by zero", "error"),
    ("启动服务时报 Connection refused error，怎么排查？", "error"),
    ("CTF Web 题：flag 藏在备份文件里，从哪入手？", "ctf"),
    ("$ nmap -sV 192.168.1.10", "linux"),
    ("sudo apt update && sudo apt upgrade", "linux"),
    ("def login(username, password):\n    return username == 'admin'", "code"),
    ("<?php echo $_GET['id']; ?>", "code"),
    ("TCP 三次握手的过程是怎样的？", "protocol"),
    ("DNS 解析为什么有时会失败？", "protocol"),
    ("我是信安大一新生，该怎么规划学习路线？", "general"),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_classify(text, expected):
    assert classify(text) == expected
```

- [ ] **Step 1.2: 运行测试确认失败**

Run: `cd backend && ./.venv/Scripts/python -m pytest tests/test_input_classifier.py tests/test_tokens.py -q`
Expected: FAIL（`ModuleNotFoundError: app.services.input_classifier`）

- [ ] **Step 1.3: 实现**

创建 `backend/app/services/tokens.py`：

```python
import re

_CJK = re.compile(r"[\u4e00-\u9fff]")


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数：CJK 字符按 1 token，其余约 4 字符 1 token。仅用于统计展示，不追求精确。"""
    cjk = len(_CJK.findall(text))
    other = len(text) - cjk
    return max(1, cjk + round(other / 4))
```

创建 `backend/app/services/input_classifier.py`：

```python
import re
from typing import Literal

InputType = Literal["http", "error", "code", "ctf", "linux", "protocol", "general"]

# 识别顺序即优先级：报文/报错特征强，先匹配；CTF 关键词次之。
_HTTP_LINE = re.compile(r"^(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|TRACE)\s+\S+\s+HTTP/\d", re.IGNORECASE)
_HTTP_STATUS = re.compile(r"^HTTP/\d(?:\.\d)?\s+\d{3}\b", re.IGNORECASE)
_ERROR = re.compile(
    r"Traceback \(most recent call last\)|Exception in thread|"
    r"\b(?:fatal|syntax|parse|type|value|key|index|runtime|connection)\s*error\b",
    re.IGNORECASE,
)
_CTF = re.compile(r"\bctf\b|flag\{|靶场|赛题|BUUCTF|CTFHub|TryHackMe|HackTheBox|解题|writeup", re.IGNORECASE)
_LINUX = re.compile(
    r"^\s*\$\s|\b(?:sudo|apt(?:-get)?|yum|nmap|gobuster|dirb|nikto|sqlmap|curl|wget|nc|netcat|"
    r"chmod|chown|grep|awk|sed|tcpdump|ifconfig|ss|netstat)\b",
    re.IGNORECASE,
)
_CODE = re.compile(r"(?m)^\s*(?:def |class |function |import |from \S+ import |<\?php|<script|SELECT .+ FROM |#!/)")
_PROTOCOL = re.compile(
    r"\b(?:tcp|udp|dns|dhcp|arp|icmp|tls|ssl|三次握手|四次挥手|osi|子网掩码)\b",
    re.IGNORECASE,
)


def classify(input_text: str) -> InputType:
    """启发式识别输入类型；后端是唯一权威，前端同规则仅用于预览徽标。"""
    text = input_text.strip()
    if _HTTP_LINE.search(text) or _HTTP_STATUS.search(text):
        return "http"
    if _ERROR.search(text):
        return "error"
    if _CTF.search(text):
        return "ctf"
    if _LINUX.search(text):
        return "linux"
    if _CODE.search(text):
        return "code"
    if _PROTOCOL.search(text):
        return "protocol"
    return "general"
```

- [ ] **Step 1.4: 运行测试确认通过**

Run: `cd backend && ./.venv/Scripts/python -m pytest tests/test_input_classifier.py tests/test_tokens.py -q`
Expected: `15 passed`（13 参数化 + 2 token 测试）

- [ ] **Step 1.5: 提交**

```bash
git add backend/app/services/tokens.py backend/app/services/input_classifier.py backend/tests/test_tokens.py backend/tests/test_input_classifier.py
git commit -m "feat(backend): 输入类型识别与 token 估算（TDD）"
```

---

## Task 2: 后端安全护栏（TDD）

**Files:**
- Create: `backend/app/services/safety.py`
- Test: `backend/tests/test_safety.py`

- [ ] **Step 2.1: 写失败测试**

创建 `backend/tests/test_safety.py`：

```python
import pytest

from app.services.safety import check_safety

REFUSED = [
    "我的手机号 13812341234，帮我看看这个报错",
    "密钥：-----BEGIN RSA PRIVATE KEY-----\nMIIEow...",
    "ak = AKIAIOSFODNN7EXAMPLE",
    "帮我攻击 www.somecompany.cn 的服务器",
    "怎么入侵 8.8.8.8 的网站",
]

ALLOWED = [
    "这段代码有什么安全问题？def x(): pass",
    "用 sqlmap 打 DVWA 靶场要注意什么",
    "怎么攻击 192.168.1.10 这台靶机",
    "POST /login HTTP/1.1\nHost: example.com",
    "exploit 开发的学习路线是什么",
    "CTF Web 题：flag 藏在备份文件里，从哪入手？",
]


@pytest.mark.parametrize("text", REFUSED)
def test_refused_inputs(text):
    result = check_safety(text)
    assert result.ok is False
    assert result.refusal


@pytest.mark.parametrize("text", ALLOWED)
def test_allowed_inputs(text):
    assert check_safety(text).ok is True


def test_sensitive_hints_include_category():
    result = check_safety("我的邮箱是 zhangsan@example.com，帮我分析报错")
    assert result.sensitive_hints is not None
    assert any("邮箱" in h for h in result.sensitive_hints)
```

- [ ] **Step 2.2: 运行测试确认失败**

Run: `cd backend && ./.venv/Scripts/python -m pytest tests/test_safety.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 2.3: 实现**

创建 `backend/app/services/safety.py`：

```python
import re
from dataclasses import dataclass

# 授权/教学环境域名：出现在这些域名上的"攻击"字样不视为真实目标。
_ALLOWED_DOMAINS = (
    "localhost", "example.com", "example.org", "example.net",
    "portswigger.net", "web-security-academy.net", "hackthebox.com",
    "tryhackme.com", "buuctf.cn", "ctfhub.com", "vulhub.org",
    "exploit-db.com", "owasp.org", "dvwa.co.uk",
)

_SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("手机号", re.compile(r"1[3-9]\d{9}")),
    ("邮箱", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("身份证号", re.compile(r"\b\d{17}[\dXx]\b")),
    ("云厂商密钥", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("私钥", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("访问令牌", re.compile(r"\b(?:sk-[A-Za-z0-9]{20,}|ghp|gho|github_pat)_?[A-Za-z0-9]{16,}\b")),
    ("密码明文", re.compile(r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key)\s*[:=]\s*\S+")),
]

_ATTACK_VERBS = re.compile(
    r"(?i)\b(?:攻击|入侵|拿下|getshell|exploit|hack|attack|pwn|爆破|渗透|打穿|挂马|肉鸡|远控)\b"
)
_DOMAIN = re.compile(
    r"(?i)\b[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.(?:com|cn|net|org|io|me|co|cc|xyz|top|info|club|site|online|shop|vip|tech|dev|app)\b"
)
_IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


@dataclass
class SafetyResult:
    ok: bool
    refusal: str | None = None
    sensitive_hints: list[str] | None = None


def _detect_sensitive(text: str) -> list[str]:
    hits: list[str] = []
    for name, pattern in _SENSITIVE_PATTERNS:
        if pattern.search(text) and name not in hits:
            hits.append(name)
    return hits


def _is_allowed_domain(domain: str) -> bool:
    return any(domain == a or domain.endswith("." + a) for a in _ALLOWED_DOMAINS)


def _is_private_ip(ip: str) -> bool:
    parts = ip.split(".")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return False
    if len(nums) != 4 or any(n > 255 for n in nums):
        return False
    if nums[0] == 10 or nums[0] == 127:
        return True
    if nums[0] == 172 and 16 <= nums[1] <= 31:
        return True
    return nums[0] == 192 and nums[1] == 168


def _detect_real_target(text: str) -> str | None:
    """攻击意图 + 非授权目标（公网域名/公网 IP）同时命中才拒绝，避免误伤原理性问题。"""
    if not _ATTACK_VERBS.search(text):
        return None
    for m in _DOMAIN.finditer(text):
        domain = m.group(0).lower()
        if not _is_allowed_domain(domain):
            return domain
    for m in _IPV4.finditer(text):
        if not _is_private_ip(m.group(0)):
            return m.group(0)
    return None


def check_safety(input_text: str) -> SafetyResult:
    hints = _detect_sensitive(input_text)
    if hints:
        return SafetyResult(
            ok=False,
            sensitive_hints=hints,
            refusal=(
                f"检测到输入可能包含敏感信息（{'、'.join(hints)}），已阻止提交以保护你的隐私。"
                "请脱敏后再试：把真实值替换为占位符（如 138****1234、password=***）。"
            ),
        )
    target = _detect_real_target(input_text)
    if target:
        return SafetyResult(
            ok=False,
            refusal=(
                f"检测到输入疑似指向真实目标（{target}）。SecMate 仅支持授权环境（靶场）下的学习分析，"
                "不协助针对真实系统的攻击。你可以：1) 换成授权靶场（DVWA、BUUCTF、TryHackMe、HackTheBox Academy 等）提问；"
                "2) 只问原理性问题（去掉目标地址）。"
            ),
        )
    return SafetyResult(ok=True)
```

- [ ] **Step 2.4: 运行测试确认通过**

Run: `cd backend && ./.venv/Scripts/python -m pytest tests/test_safety.py -q`
Expected: `12 passed`

- [ ] **Step 2.5: 提交**

```bash
git add backend/app/services/safety.py backend/tests/test_safety.py
git commit -m "feat(backend): 安全护栏——敏感信息检测与真实目标拒绝（TDD）"
```

---

## Task 3: 后端 IP 限流（TDD）

**Files:**
- Create: `backend/app/services/rate_limiter.py`
- Test: `backend/tests/test_rate_limiter.py`
- Modify: `backend/app/core/config.py`（增加配置项）
- Modify: `backend/.env.example`（增加配置项）

- [ ] **Step 3.1: 写失败测试**

创建 `backend/tests/test_rate_limiter.py`：

```python
from app.services.rate_limiter import SlidingWindowLimiter


def test_allows_up_to_limit():
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60.0)
    assert limiter.allow("ip-a") is True
    assert limiter.allow("ip-a") is True
    assert limiter.allow("ip-a") is True
    assert limiter.allow("ip-a") is False


def test_different_keys_isolated():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60.0)
    assert limiter.allow("ip-a") is True
    assert limiter.allow("ip-b") is True


def test_window_expiry_frees_slots():
    limiter = SlidingWindowLimiter(limit=1, window_seconds=0.01)
    assert limiter.allow("ip-a") is True
    assert limiter.allow("ip-a") is False
    import time

    time.sleep(0.02)
    assert limiter.allow("ip-a") is True


def test_remaining_counts_down():
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60.0)
    limiter.allow("ip-a")
    assert limiter.remaining("ip-a") == 1
```

- [ ] **Step 3.2: 运行测试确认失败**

Run: `cd backend && ./.venv/Scripts/python -m pytest tests/test_rate_limiter.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3.3: 实现**

创建 `backend/app/services/rate_limiter.py`：

```python
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from app.core.config import get_settings


@dataclass
class SlidingWindowLimiter:
    """单进程内存滑动窗口限流；MVP 单实例部署够用，阶段后如需多实例再换 Redis。"""

    limit: int
    window_seconds: float
    _hits: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def _prune(self, key: str, now: float) -> None:
        dq = self._hits[key]
        while dq and now - dq[0] > self.window_seconds:
            dq.popleft()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        self._prune(key, now)
        dq = self._hits[key]
        if len(dq) >= self.limit:
            return False
        dq.append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        self._prune(key, now)
        return max(0, self.limit - len(self._hits[key]))


_limiter: SlidingWindowLimiter | None = None


def get_limiter() -> SlidingWindowLimiter:
    """按当前配置惰性创建单例；配置变更或测试需重建时调用 reset_limiter()。"""
    global _limiter
    if _limiter is None:
        _limiter = SlidingWindowLimiter(
            limit=get_settings().rate_limit_per_minute, window_seconds=60.0
        )
    return _limiter


def reset_limiter() -> None:
    global _limiter
    _limiter = None
```

修改 `backend/app/core/config.py`，在 Supabase 配置段之前插入：

```python
    # 限流：每 IP 每分钟允许的分析请求数
    rate_limit_per_minute: int = 10
```

修改 `backend/.env.example`，在 AI Provider 段之后插入：

```ini
# 限流：每 IP 每分钟允许的分析请求数
RATE_LIMIT_PER_MINUTE=10
```

- [ ] **Step 3.4: 运行测试确认通过**

Run: `cd backend && ./.venv/Scripts/python -m pytest tests/test_rate_limiter.py -q`
Expected: `4 passed`

- [ ] **Step 3.5: 提交**

```bash
git add backend/app/services/rate_limiter.py backend/tests/test_rate_limiter.py backend/app/core/config.py backend/.env.example
git commit -m "feat(backend): IP 级滑动窗口限流（可配置）"
```

---

## Task 4: 后端内置提示词（与种子数据一致）

**Files:**
- Create: `backend/app/prompts/system_prompts.py`
- Test: `backend/tests/test_system_prompts.py`

- [ ] **Step 4.1: 写失败测试**

创建 `backend/tests/test_system_prompts.py`：

```python
import pytest

from app.prompts.system_prompts import DISCLAIMER, SYSTEM_PROMPTS

SCENES = ["general", "http", "error", "code", "ctf", "linux", "protocol"]
SECTIONS = ["问题分析", "技术原理解释", "学习方向", "排查思路", "修复建议", "相关知识点", "推荐练习环境"]


@pytest.mark.parametrize("scene", SCENES)
def test_every_scene_has_seven_sections(scene):
    prompt = SYSTEM_PROMPTS[scene]
    for section in SECTIONS:
        assert section in prompt, f"{scene} 缺少段落: {section}"


@pytest.mark.parametrize("scene", SCENES)
def test_every_scene_has_safety_red_lines(scene):
    assert "授权" in SYSTEM_PROMPTS[scene]


def test_disclaimer_mentions_authorized_learning():
    assert "授权环境" in DISCLAIMER
```

- [ ] **Step 4.2: 运行测试确认失败**

Run: `cd backend && ./.venv/Scripts/python -m pytest tests/test_system_prompts.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 4.3: 实现**

创建 `backend/app/prompts/system_prompts.py`。内容与 `database/seed_prompts.sql` 六场景完全一致（阶段5 迁移到数据库后台管理，届时本模块删除）：

```python
"""阶段3 内置提示词：与 database/seed_prompts.sql 保持一致。阶段5 将迁移到数据库 prompts 表。"""

DISCLAIMER = "以上内容仅供授权环境下的学习与防御研究使用。"

_SECTIONS = """输出格式（按顺序使用 Markdown 二级标题）：
1. 问题分析
2. 技术原理解释
3. 学习方向
4. 排查思路
5. 修复建议
6. 相关知识点
7. 推荐练习环境

风格要求：中文、简洁、面向初学者；代码用带语言标注的代码块；结尾附一行免责声明："以上内容仅供授权环境下的学习与防御研究使用。" """

_RED_LINES = """安全红线（必须遵守）：
1. 只提供教育与防御视角的内容；不提供针对真实、未授权目标的攻击步骤、利用代码或绕过手段。
2. 所有实操建议只指向授权环境，例如：本地 Docker 靶场、DVWA、PortSwigger Web Security Academy、HackTheBox Academy、TryHackMe、BUUCTF、CTFHub 等。
3. 用户输入若涉及攻击真实目标，礼貌拒绝并引导到授权环境学习。
4. 不请求、不保存任何真实凭据。"""

SYSTEM_PROMPTS: dict[str, str] = {
    "general": (
        "你是 SecMate，一名耐心的 AI 网络安全学习导师，服务对象是信息安全学生与 CTF 初学者。\n\n"
        f"{_RED_LINES}\n\n{_SECTIONS}"
    ),
    "http": (
        "你是 SecMate 的 HTTP 协议分析导师，服务对象是信息安全学生与 CTF 初学者。当前输入是一段 HTTP 请求/响应报文。\n\n"
        "安全红线（必须遵守）：\n"
        "1. 只做报文结构与协议语义的解读，不提供针对真实目标的攻击步骤。\n"
        "2. 实操建议只指向授权环境（DVWA、PortSwigger Web Security Academy、本地靶场等）。\n"
        "3. 若报文包含真实凭据或指向真实生产系统，提醒用户不要提交敏感信息。\n\n"
        "输出格式（按顺序使用 Markdown 二级标题）：\n"
        "1. 问题分析（逐行解读请求行/头/体）\n"
        "2. 技术原理解释（涉及的协议与机制）\n"
        "3. 学习方向（该报文涉及的安全主题）\n"
        "4. 排查思路（如何验证你的理解）\n"
        "5. 修复建议（服务端可采取的防御措施）\n"
        "6. 相关知识点\n"
        "7. 推荐练习环境\n\n"
        f"风格要求：中文、简洁；代码块标注语言；结尾附免责声明：\"{DISCLAIMER}\""
    ),
    "error": (
        "你是 SecMate 的报错诊断导师，服务对象是信息安全学生与 CTF 初学者。当前输入是一段 Web/程序报错信息。\n\n"
        "安全红线（必须遵守）：\n"
        "1. 解释报错的原理与信息泄露风险，不提供利用真实系统的攻击步骤。\n"
        "2. 实操建议只指向授权环境。\n"
        "3. 提醒用户：报错中可能包含敏感信息（路径、版本、SQL 语句），提交前应脱敏。\n\n"
        "输出格式（按顺序使用 Markdown 二级标题）：\n"
        "1. 问题分析（报错含义与可能根因）\n"
        "2. 技术原理解释\n"
        "3. 学习方向\n"
        "4. 排查思路\n"
        "5. 修复建议（含生产环境如何安全处理报错）\n"
        "6. 相关知识点\n"
        "7. 推荐练习环境\n\n"
        f"风格要求：中文、简洁；代码块标注语言；结尾附免责声明：\"{DISCLAIMER}\""
    ),
    "code": (
        "你是 SecMate 的代码安全导师，服务对象是信息安全学生与 CTF 初学者。当前输入是一段代码片段。\n\n"
        "安全红线（必须遵守）：\n"
        "1. 以\"发现风险 + 防御写法\"的方式讲解，不提供针对真实系统的利用代码。\n"
        "2. 实操建议只指向授权环境。\n\n"
        "输出格式（按顺序使用 Markdown 二级标题）：\n"
        "1. 问题分析（代码意图与潜在风险点）\n"
        "2. 技术原理解释\n"
        "3. 学习方向\n"
        "4. 排查思路（如何验证风险存在）\n"
        "5. 修复建议（给出安全写法示例）\n"
        "6. 相关知识点\n"
        "7. 推荐练习环境\n\n"
        f"风格要求：中文、简洁；代码块标注语言；结尾附免责声明：\"{DISCLAIMER}\""
    ),
    "ctf": (
        "你是 SecMate 的 CTF 引导教练，服务对象是 CTF 初学者。当前输入是一道 CTF 题目描述。\n\n"
        "教学原则（必须遵守）：\n"
        "1. 默认采用\"思路引导\"模式：给方向、讲原理、提示关键点，不直接给答案或 flag；若用户明确要求完整讲解，再切换到\"讲解模式\"讲透。\n"
        "2. 只讨论 CTF 与靶场环境中的题目；不协助攻击真实系统。\n"
        "3. 推荐的练习环境：BUUCTF、CTFHub、PortSwigger Web Security Academy、TryHackMe、HackTheBox Academy 等。\n\n"
        "输出格式（按顺序使用 Markdown 二级标题）：\n"
        "1. 问题分析（题面解读与考点定位）\n"
        "2. 技术原理解释\n"
        "3. 学习方向\n"
        "4. 排查思路（分步提示，由浅入深）\n"
        "5. 修复建议（对应防御视角）\n"
        "6. 相关知识点\n"
        "7. 推荐练习环境（同类型进阶题）\n\n"
        f"风格要求：中文、简洁、鼓励式语气；代码块标注语言；结尾附免责声明：\"{DISCLAIMER}\""
    ),
    "linux": (
        "你是 SecMate 的 Linux 安全导师，服务对象是信息安全学生与 CTF 初学者。当前输入是一条或多条 Linux 命令。\n\n"
        "安全红线（必须遵守）：\n"
        "1. 解释命令作用、参数含义与安全注意点；不提供针对真实系统的入侵指令。\n"
        "2. 涉及提权、内网等主题时，只讲解原理并指向授权靶场（TryHackMe、HackTheBox Academy 等）。\n\n"
        "输出格式（按顺序使用 Markdown 二级标题）：\n"
        "1. 问题分析（命令意图与逐段解读）\n"
        "2. 技术原理解释\n"
        "3. 学习方向\n"
        "4. 排查思路\n"
        "5. 修复建议（对应防御与加固视角）\n"
        "6. 相关知识点\n"
        "7. 推荐练习环境\n\n"
        f"风格要求：中文、简洁；代码块标注语言；结尾附免责声明：\"{DISCLAIMER}\""
    ),
    "protocol": (
        "你是 SecMate 的网络协议导师，服务对象是信息安全学生与 CTF 初学者。当前输入是一个网络协议相关的问题。\n\n"
        "安全红线（必须遵守）：\n"
        "1. 讲解协议原理、报文结构与常见缺陷，不提供针对真实网络的攻击步骤。\n"
        "2. 抓包、重放等实操建议只指向授权环境（本地实验网络、靶场流量）。\n\n"
        "输出格式（按顺序使用 Markdown 二级标题）：\n"
        "1. 问题分析\n"
        "2. 技术原理解释（协议工作流程）\n"
        "3. 学习方向\n"
        "4. 排查思路（可用 Wireshark/tcpdump 等工具验证）\n"
        "5. 修复建议（协议层面的防御措施）\n"
        "6. 相关知识点\n"
        "7. 推荐练习环境\n\n"
        f"风格要求：中文、简洁；代码块标注语言；结尾附免责声明：\"{DISCLAIMER}\""
    ),
}
```

- [ ] **Step 4.4: 运行测试确认通过**

Run: `cd backend && ./.venv/Scripts/python -m pytest tests/test_system_prompts.py -q`
Expected: `14 passed`

- [ ] **Step 4.5: 提交**

```bash
git add backend/app/prompts/system_prompts.py backend/tests/test_system_prompts.py
git commit -m "feat(backend): 六场景内置提示词（七段式 + 安全红线）"
```

---

## Task 5: 后端分析记录落库（TDD）

**Files:**
- Create: `backend/app/services/recorder.py`
- Test: `backend/tests/test_recorder.py`

- [ ] **Step 5.1: 写失败测试**

创建 `backend/tests/test_recorder.py`：

```python
import asyncio
import json

import httpx
import pytest

from app.core.config import get_settings
from app.services.recorder import record_analysis


@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_skips_when_supabase_not_configured():
    result = asyncio.run(record_analysis(
        input_type="general", input_text="hi", result_md="ok",
        model="deepseek-chat", tokens_in=1, tokens_out=1,
    ))
    assert result is None


def test_posts_to_postgrest_with_service_role(monkeypatch):
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json=[{"id": 42}])

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key-123")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(record_analysis(
        input_type="http", input_text="GET / HTTP/1.1", result_md="ok",
        model="deepseek-chat", tokens_in=10, tokens_out=20, http_client=client,
    ))

    assert result == 42
    assert captured["url"].endswith("/rest/v1/analyses")
    assert captured["headers"]["apikey"] == "service-role-key-123"
    assert captured["headers"]["authorization"] == "Bearer service-role-key-123"
    assert captured["body"]["input_type"] == "http"
    assert captured["body"]["user_id"] is None
    assert captured["body"]["result_md"] == "ok"


def test_db_failure_returns_none(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    monkeypatch.setenv("SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key-123")
    get_settings.cache_clear()

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = asyncio.run(record_analysis(
        input_type="general", input_text="hi", result_md="ok",
        model="deepseek-chat", tokens_in=1, tokens_out=1, http_client=client,
    ))
    assert result is None
```

- [ ] **Step 5.2: 运行测试确认失败**

Run: `cd backend && ./.venv/Scripts/python -m pytest tests/test_recorder.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 5.3: 实现**

创建 `backend/app/services/recorder.py`：

```python
import httpx

from app.core.config import get_settings

_INSERT_PATH = "/rest/v1/analyses"


async def record_analysis(
    *,
    input_type: str,
    input_text: str,
    result_md: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    http_client: httpx.AsyncClient | None = None,
) -> int | None:
    """匿名分析落库（PostgREST + service_role，可绕过 RLS）。未配置 Supabase 时跳过，保证本地可无库运行。"""
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        print("[SecMate] Supabase 未配置，跳过分析落库")
        return None

    payload = {
        "user_id": None,
        "input_type": input_type,
        "input_text": input_text,
        "result_md": result_md,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }
    headers = {
        "apikey": s.supabase_service_role_key,
        "Authorization": f"Bearer {s.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    async def _post(client: httpx.AsyncClient) -> int | None:
        try:
            resp = await client.post(
                f"{s.supabase_url.rstrip('/')}{_INSERT_PATH}",
                json=payload,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            print(f"[SecMate] 落库失败（网络）: {exc}")
            return None
        if resp.status_code >= 400:
            print(f"[SecMate] 落库失败: {resp.status_code} {resp.text[:300]}")
            return None
        try:
            rows = resp.json()
            return int(rows[0]["id"]) if rows else None
        except (ValueError, KeyError, IndexError):
            return None

    if http_client is not None:
        return await _post(http_client)
    async with httpx.AsyncClient(timeout=10.0) as client:
        return await _post(client)
```

- [ ] **Step 5.4: 运行测试确认通过**

Run: `cd backend && ./.venv/Scripts/python -m pytest tests/test_recorder.py -q`
Expected: `3 passed`

- [ ] **Step 5.5: 提交**

```bash
git add backend/app/services/recorder.py backend/tests/test_recorder.py
git commit -m "feat(backend): 匿名分析记录落库（PostgREST，未配置跳过）"
```

---

## Task 6: 后端分析 SSE 路由（TDD 集成测试）

**Files:**
- Create: `backend/app/schemas/analysis.py`
- Create: `backend/app/api/routes/analysis.py`
- Test: `backend/tests/test_analysis_route.py`
- Modify: `backend/app/main.py`（注册路由）

- [ ] **Step 6.1: 写失败测试**

创建 `backend/tests/test_analysis_route.py`：

```python
import json

import httpx
import pytest
from fastapi.testclient import TestClient

import app.api.routes.analysis as analysis_module
from app.core.config import get_settings
from app.main import app
from app.providers.openai_compat import OpenAICompatProvider
from app.services.rate_limiter import reset_limiter

client = TestClient(app)


def make_streaming_transport(chunks: list[str], status: int = 200) -> httpx.MockTransport:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        captured["url"] = str(request.url)

        def body() -> bytes:
            for c in chunks:
                chunk = {"choices": [{"delta": {"content": c}}]}
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode()
            yield b"data: [DONE]\n\n"

        return httpx.Response(
            status,
            headers={"content-type": "text/event-stream"},
            content=b"".join(body()),
        )

    return httpx.MockTransport(handler), captured


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.split("\n\n"):
        event = data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if event and data is not None:
            events.append((event, data))
    return events


@pytest.fixture(autouse=True)
def fresh_limiter(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_PER_MINUTE", raising=False)
    get_settings.cache_clear()
    reset_limiter()
    yield
    reset_limiter()
    get_settings.cache_clear()


def test_analysis_streams_meta_delta_done(monkeypatch):
    transport, captured = make_streaming_transport(["你", "好，世界"])
    provider = OpenAICompatProvider(
        base_url="https://mock.local/v1", api_key="k", model="deepseek-chat",
        http_client=httpx.AsyncClient(transport=transport),
    )
    monkeypatch.setattr(analysis_module, "get_provider", lambda: provider)

    resp = client.post("/api/v1/analysis", json={
        "input_text": "POST /login HTTP/1.1\nHost: 192.168.1.10\nUser-Agent: curl/8.0",
    })
    assert resp.status_code == 200
    events = parse_sse(resp.text)
    assert events[0][0] == "meta"
    assert events[0][1]["input_type"] == "http"
    deltas = [d["content"] for e, d in events if e == "delta"]
    assert "".join(deltas) == "你好，世界"
    assert events[-1][0] == "done"

    # 系统提示词为 http 场景且包含安全红线；用户输入原样透传
    messages = captured["payload"]["messages"]
    assert messages[0]["role"] == "system"
    assert "HTTP" in messages[0]["content"]
    assert "授权环境" in messages[0]["content"]
    assert messages[1]["content"].startswith("POST /login")


def test_sensitive_input_refused_with_400():
    resp = client.post("/api/v1/analysis", json={
        "input_text": "我的手机号 13812341234，帮忙分析这个报错",
    })
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "refused"
    assert "敏感信息" in resp.json()["detail"]["message"]


def test_rate_limit_returns_429(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")
    get_settings.cache_clear()
    reset_limiter()
    transport, _ = make_streaming_transport(["ok"])
    provider = OpenAICompatProvider(
        base_url="https://mock.local/v1", api_key="k", model="deepseek-chat",
        http_client=httpx.AsyncClient(transport=transport),
    )
    monkeypatch.setattr(analysis_module, "get_provider", lambda: provider)

    payload = {"input_text": "TCP 三次握手的过程是怎样的？", "input_type": "protocol"}
    first = client.post("/api/v1/analysis", json=payload)
    second = client.post("/api/v1/analysis", json=payload)
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"]["code"] == "rate_limited"


def test_provider_error_emits_error_event(monkeypatch):
    transport, _ = make_streaming_transport([], status=401)
    provider = OpenAICompatProvider(
        base_url="https://mock.local/v1", api_key="k", model="deepseek-chat",
        http_client=httpx.AsyncClient(transport=transport),
    )
    monkeypatch.setattr(analysis_module, "get_provider", lambda: provider)

    resp = client.post("/api/v1/analysis", json={"input_text": "什么是 SQL 注入？"})
    assert resp.status_code == 200
    events = parse_sse(resp.text)
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "provider_error"


def test_too_long_input_rejected():
    resp = client.post("/api/v1/analysis", json={"input_text": "a" * 8001})
    assert resp.status_code == 422
```

- [ ] **Step 6.2: 运行测试确认失败**

Run: `cd backend && ./.venv/Scripts/python -m pytest tests/test_analysis_route.py -q`
Expected: FAIL（`app.api.routes.analysis` 不存在 / 路由 404）

- [ ] **Step 6.3: 实现**

创建 `backend/app/schemas/analysis.py`：

```python
from typing import Literal

from pydantic import BaseModel, Field

InputType = Literal["http", "error", "code", "ctf", "linux", "protocol", "general"]


class AnalysisRequest(BaseModel):
    """分析请求。input_type 为客户端猜测值，后端会重新识别并以 meta 事件返回最终类型。"""

    input_text: str = Field(min_length=1, max_length=8000)
    input_type: InputType | None = None
```

创建 `backend/app/api/routes/analysis.py`：

```python
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.providers.base import ProviderError
from app.providers.factory import get_provider
from app.prompts.system_prompts import SYSTEM_PROMPTS
from app.schemas.analysis import AnalysisRequest
from app.services.input_classifier import classify
from app.services.rate_limiter import get_limiter
from app.services.recorder import record_analysis
from app.services.safety import check_safety
from app.services.tokens import estimate_tokens

router = APIRouter(tags=["analysis"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/analysis")
async def analyze(payload: AnalysisRequest, request: Request):
    ip = _client_ip(request)

    if not get_limiter().allow(ip):
        raise HTTPException(
            status_code=429,
            detail={"code": "rate_limited", "message": "请求过于频繁，请稍后再试。"},
        )

    safety = check_safety(payload.input_text)
    if not safety.ok:
        raise HTTPException(
            status_code=400,
            detail={"code": "refused", "message": safety.refusal},
        )

    input_type = classify(payload.input_text)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS[input_type]},
        {"role": "user", "content": payload.input_text},
    ]

    async def gen() -> AsyncIterator[str]:
        chunks: list[str] = []
        try:
            yield _sse("meta", {"input_type": input_type})
            provider = get_provider()
            async for chunk in provider.stream_chat(messages):
                chunks.append(chunk)
                yield _sse("delta", {"content": chunk})
            full = "".join(chunks)
            tokens_out = estimate_tokens(full)
            analysis_id = await record_analysis(
                input_type=input_type,
                input_text=payload.input_text,
                result_md=full,
                model=provider.model,
                tokens_in=estimate_tokens(payload.input_text),
                tokens_out=tokens_out,
            )
            yield _sse("done", {"analysis_id": analysis_id, "tokens_out": tokens_out})
        except ProviderError as exc:
            yield _sse("error", {"code": "provider_error", "message": f"AI 服务暂时不可用：{exc}"})
        except Exception as exc:  # noqa: BLE001 — 流中途异常统一转为 error 事件，不输出输入内容
            print(f"[SecMate] analysis stream error: {exc!r}")
            yield _sse("error", {"code": "internal_error", "message": "分析过程中出现异常，请稍后重试。"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
```

修改 `backend/app/main.py`，将：

```python
from app.api.routes import health
```

改为：

```python
from app.api.routes import analysis, health
```

并将：

```python
app.include_router(health.router, prefix="/api/v1")
```

改为：

```python
app.include_router(health.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
```

- [ ] **Step 6.4: 运行测试确认通过**

Run: `cd backend && ./.venv/Scripts/python -m pytest tests/test_analysis_route.py -q`
Expected: `5 passed`

- [ ] **Step 6.5: 运行全量测试**

Run: `cd backend && ./.venv/Scripts/python -m pytest -q`
Expected: 全部通过（既有 3 + 新增 ≈ 41）

- [ ] **Step 6.6: 提交**

```bash
git add backend/app/schemas/analysis.py backend/app/api/routes/analysis.py backend/tests/test_analysis_route.py backend/app/main.py
git commit -m "feat(backend): POST /api/v1/analysis SSE 流式分析接口"
```

---

## Task 7: 前端依赖与主题/Markdown 基础组件

**Files:**
- Modify: `frontend/package.json`（安装依赖）
- Create: `frontend/src/components/theme-provider.tsx`
- Create: `frontend/src/components/theme-toggle.tsx`
- Create: `frontend/src/components/markdown.tsx`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 7.1: 安装依赖**

Run: `cd frontend && npm install react-markdown remark-gfm rehype-highlight next-themes`
Expected: 安装成功，package.json 新增 4 个依赖（react-markdown ^9、remark-gfm ^4、rehype-highlight ^7、next-themes ^0.4）

- [ ] **Step 7.2: ThemeProvider 与主题切换**

创建 `frontend/src/components/theme-provider.tsx`：

```tsx
"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      {children}
    </NextThemesProvider>
  );
}
```

创建 `frontend/src/components/theme-toggle.tsx`：

```tsx
"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) {
    return <Button variant="ghost" size="icon-sm" aria-label="切换主题" className="text-muted-foreground" />;
  }
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-label="切换主题"
      className="text-muted-foreground"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
    >
      {resolvedTheme === "dark" ? <Sun /> : <Moon />}
    </Button>
  );
}
```

- [ ] **Step 7.3: Markdown 渲染组件**

创建 `frontend/src/components/markdown.tsx`：

```tsx
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

export function Markdown({ content }: { content: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
```

- [ ] **Step 7.4: globals.css 追加样式**

在 `frontend/src/app/globals.css` 第一行（`@import "tw-animate-css";` 之前）插入：

```css
@import "highlight.js/styles/github-dark.css";
```

在文件末尾追加：

```css
@layer components {
  /* 分析结果 Markdown 排版；代码块固定深色底，与 highlight.js 深色主题一致 */
  .markdown-body {
    @apply text-sm leading-relaxed text-foreground;
  }
  .markdown-body h2 {
    @apply mt-8 mb-3 border-b border-border pb-1.5 text-lg font-semibold first:mt-0;
  }
  .markdown-body h3 {
    @apply mt-6 mb-2 text-base font-semibold;
  }
  .markdown-body p {
    @apply my-3;
  }
  .markdown-body ul,
  .markdown-body ol {
    @apply my-3 pl-6;
  }
  .markdown-body ul {
    @apply list-disc;
  }
  .markdown-body ol {
    @apply list-decimal;
  }
  .markdown-body li {
    @apply my-1;
  }
  .markdown-body code {
    @apply rounded bg-muted px-1 py-0.5 font-mono text-[0.85em];
  }
  .markdown-body pre {
    @apply my-4 overflow-x-auto rounded-lg border border-border bg-zinc-950 p-4 text-[13px] leading-relaxed;
  }
  .markdown-body pre code {
    @apply bg-transparent p-0 text-inherit;
  }
  .markdown-body table {
    @apply my-4 w-full border-collapse text-sm;
  }
  .markdown-body th,
  .markdown-body td {
    @apply border border-border px-3 py-1.5 text-left;
  }
  .markdown-body th {
    @apply bg-muted font-medium;
  }
  .markdown-body blockquote {
    @apply my-4 border-l-2 border-primary/40 pl-4 text-muted-foreground;
  }
  .markdown-body a {
    @apply text-primary underline underline-offset-4;
  }
  .markdown-body hr {
    @apply my-6 border-border;
  }
}
```

- [ ] **Step 7.5: layout.tsx 接入主题**

将 `frontend/src/app/layout.tsx` 中 `<html lang="zh-CN">` 改为 `<html lang="zh-CN" suppressHydrationWarning>`，将 `{children}` 包进 ThemeProvider，并更新 metadata：

```tsx
import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

import { ThemeProvider } from "@/components/theme-provider";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "SecMate - AI Powered Cyber Security Learning Assistant",
  description:
    "SecMate 把看不懂的报错、请求、命令、CTF 题目变成讲得清原理、给得出方向、指得明练习环境的学习材料——面向信安学生与 CTF 初学者的 AI 网络安全学习助手。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 7.6: 构建验证**

Run: `cd frontend && npm run build`
Expected: 构建成功（若 highlight.js CSS 引入报错，确认该文件位于 node_modules/highlight.js/styles/ 且 @import 行在所有其他语句之前）

- [ ] **Step 7.7: 提交**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/theme-provider.tsx frontend/src/components/theme-toggle.tsx frontend/src/components/markdown.tsx frontend/src/app/layout.tsx frontend/src/app/globals.css
git commit -m "feat(frontend): 主题切换与 Markdown 渲染基础（代码高亮）"
```

---

## Task 8: 前端类型识别、示例数据与 SSE 客户端

**Files:**
- Create: `frontend/src/lib/input-classifier.ts`
- Create: `frontend/src/lib/examples.ts`
- Create: `frontend/src/lib/api.ts`

- [ ] **Step 8.1: 类型识别（与后端同规则）**

创建 `frontend/src/lib/input-classifier.ts`：

```ts
export type InputType =
  | "http"
  | "error"
  | "code"
  | "ctf"
  | "linux"
  | "protocol"
  | "general";

export const INPUT_TYPE_LABELS: Record<InputType, string> = {
  http: "HTTP 报文",
  error: "报错信息",
  code: "代码片段",
  ctf: "CTF 题目",
  linux: "Linux 命令",
  protocol: "网络协议",
  general: "通用问题",
};

export function isInputType(value: unknown): value is InputType {
  return typeof value === "string" && value in INPUT_TYPE_LABELS;
}

const RE_HTTP_LINE = /^(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|TRACE)\s+\S+\s+HTTP\/\d/i;
const RE_HTTP_STATUS = /^HTTP\/\d(?:\.\d)?\s+\d{3}\b/i;
const RE_ERROR =
  /Traceback \(most recent call last\)|Exception in thread|\b(?:fatal|syntax|parse|type|value|key|index|runtime|connection)\s*error\b/i;
const RE_CTF = /\bctf\b|flag\{|靶场|赛题|BUUCTF|CTFHub|TryHackMe|HackTheBox|解题|writeup/i;
const RE_LINUX =
  /^\s*\$\s|\b(?:sudo|apt(?:-get)?|yum|nmap|gobuster|dirb|nikto|sqlmap|curl|wget|nc|netcat|chmod|chown|grep|awk|sed|tcpdump|ifconfig|ss|netstat)\b/i;
const RE_CODE = /^\s*(?:def |class |function |import |from \S+ import |<\?php|<script|SELECT .+ FROM |#!\/)/m;
const RE_PROTOCOL = /\b(?:tcp|udp|dns|dhcp|arp|icmp|tls|ssl|三次握手|四次挥手|osi|子网掩码)\b/i;

/** 仅用于分析前 UI 徽标预览；后端识别结果以 meta 事件为准。 */
export function classifyInput(text: string): InputType {
  const t = text.trim();
  if (RE_HTTP_LINE.test(t) || RE_HTTP_STATUS.test(t)) return "http";
  if (RE_ERROR.test(t)) return "error";
  if (RE_CTF.test(t)) return "ctf";
  if (RE_LINUX.test(t)) return "linux";
  if (RE_CODE.test(t)) return "code";
  if (RE_PROTOCOL.test(t)) return "protocol";
  return "general";
}
```

- [ ] **Step 8.2: 示例数据（注意：示例不得触发后端安全拦截）**

创建 `frontend/src/lib/examples.ts`：

```ts
import type { InputType } from "@/lib/input-classifier";

export interface Example {
  label: string;
  type: InputType;
  text: string;
}

export const EXAMPLES: Example[] = [
  {
    label: "HTTP 报文",
    type: "http",
    text: "POST /login HTTP/1.1\nHost: 192.168.1.10\nContent-Type: application/x-www-form-urlencoded\nContent-Length: 32\n\nusername=admin&login=admin",
  },
  {
    label: "报错信息",
    type: "error",
    text: 'Traceback (most recent call last):\n  File "app.py", line 42, in <module>\n    value = int(user_input)\nValueError: invalid literal for int() with base 10: \'abc\'',
  },
  {
    label: "CTF 题目",
    type: "ctf",
    text: "CTF Web 题：靶场提示 flag 藏在某个备份文件里，页面上只有一个登录框，尝试经典弱口令无效，下一步该从哪个方向入手？",
  },
];
```

- [ ] **Step 8.3: SSE 流式客户端**

创建 `frontend/src/lib/api.ts`：

```ts
import type { InputType } from "@/lib/input-classifier";

export interface StreamCallbacks {
  onMeta?: (inputType: InputType) => void;
  onDelta?: (content: string) => void;
  onDone?: (payload: { analysisId: number | null; tokensOut: number }) => void;
  onError?: (code: string, message: string) => void;
}

export class ApiError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

export async function streamAnalysis(
  inputText: string,
  inputType: InputType | null,
  cb: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input_text: inputText, input_type: inputType }),
    signal,
  });

  if (!resp.ok) {
    let code = "unknown";
    let message = `请求失败（HTTP ${resp.status}）`;
    try {
      const body = await resp.json();
      const detail = body.detail ?? body;
      code = detail.code ?? code;
      message = detail.message ?? message;
    } catch {
      // 非 JSON 错误体，保留默认文案
    }
    throw new ApiError(code, message);
  }

  if (!resp.body) {
    throw new ApiError("stream_error", "当前浏览器不支持流式响应");
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (!data) continue;
      let payload: Record<string, unknown>;
      try {
        payload = JSON.parse(data);
      } catch {
        continue;
      }
      if (event === "meta") cb.onMeta?.(payload.input_type as InputType);
      else if (event === "delta") cb.onDelta?.(String(payload.content ?? ""));
      else if (event === "done") cb.onDone?.(payload as { analysisId: number | null; tokensOut: number });
      else if (event === "error") cb.onError?.(String(payload.code ?? "unknown"), String(payload.message ?? "未知错误"));
    }
  }
}
```

- [ ] **Step 8.4: 构建验证**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 8.5: 提交**

```bash
git add frontend/src/lib/input-classifier.ts frontend/src/lib/examples.ts frontend/src/lib/api.ts
git commit -m "feat(frontend): 类型识别、示例数据与 SSE 流式客户端"
```

---

## Task 9: 前端代理路由

**Files:**
- Create: `frontend/src/app/api/analyze/route.ts`
- Modify: `frontend/.env.local.example`

- [ ] **Step 9.1: 实现代理路由**

创建 `frontend/src/app/api/analyze/route.ts`：

```ts
import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// 架构约定：前端代理后端（隐藏后端地址、统一 CORS、SSE 透传）
const BACKEND_API_URL = process.env.BACKEND_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify({ detail: { code: "invalid_request", message: "请求体不是合法 JSON" } }),
      { status: 400, headers: { "Content-Type": "application/json; charset=utf-8" } },
    );
  }

  const upstream = await fetch(`${BACKEND_API_URL}/api/v1/analysis`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Forwarded-For":
        request.headers.get("x-forwarded-for") ||
        request.headers.get("x-real-ip") ||
        "127.0.0.1",
    },
    body: JSON.stringify(body),
    signal: request.signal,
  });

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text();
    return new Response(
      text || JSON.stringify({ detail: { code: "upstream_error", message: "后端服务不可用，请稍后重试" } }),
      { status: upstream.status, headers: { "Content-Type": "application/json; charset=utf-8" } },
    );
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
```

- [ ] **Step 9.2: 更新 .env.local.example**

`frontend/.env.local.example` 追加说明（后端端口可按需改）：

```ini
# 后端地址（本机开发默认 8000；若 8000 被占用可改 8001）
BACKEND_API_URL=http://localhost:8000
```

- [ ] **Step 9.3: 构建验证**

Run: `cd frontend && npm run build`
Expected: 构建成功，无 lint 错误

- [ ] **Step 9.4: 提交**

```bash
git add frontend/src/app/api/analyze/route.ts frontend/.env.local.example
git commit -m "feat(frontend): /api/analyze 代理路由（SSE 透传）"
```

---

## Task 10: 前端分析页（M2）

**Files:**
- Create: `frontend/src/components/site-header.tsx`
- Create: `frontend/src/components/analysis-input.tsx`
- Create: `frontend/src/components/analysis-result.tsx`
- Create: `frontend/src/components/analyze-client.tsx`
- Create: `frontend/src/app/analyze/page.tsx`

- [ ] **Step 10.1: 顶部导航**

创建 `frontend/src/components/site-header.tsx`：

```tsx
import Link from "next/link";
import { ShieldCheck } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <ShieldCheck className="size-5 text-emerald-500" />
          <span>SecMate</span>
        </Link>
        <nav className="flex items-center gap-3">
          <Link
            href="/analyze"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            开始分析
          </Link>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
```

- [ ] **Step 10.2: 输入区**

创建 `frontend/src/components/analysis-input.tsx`：

```tsx
"use client";

import { Loader2, Send } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { EXAMPLES } from "@/lib/examples";
import { classifyInput, INPUT_TYPE_LABELS } from "@/lib/input-classifier";

const MAX_LENGTH = 8000;

export function AnalysisInput({
  onAnalyze,
  streaming,
  initialText = "",
}: {
  onAnalyze: (text: string) => void;
  streaming: boolean;
  initialText?: string;
}) {
  const [text, setText] = useState(initialText);
  const detected = classifyInput(text);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>粘贴你要分析的内容（报错 / 报文 / 代码 / 命令 / 题目均可）</span>
        <span className={text.length > MAX_LENGTH * 0.95 ? "text-destructive" : ""}>
          {text.length.toLocaleString()} / {MAX_LENGTH.toLocaleString()}
        </span>
      </div>
      <textarea
        value={text}
        maxLength={MAX_LENGTH}
        onChange={(e) => setText(e.target.value)}
        placeholder={'例如粘贴一段报错：\n\nTraceback (most recent call last):\n  File "app.py", line 10, in <module> ...'}
        className="h-56 w-full resize-y rounded-lg border border-input bg-card/60 p-4 font-mono text-sm outline-none transition-colors placeholder:text-muted-foreground/60 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-muted-foreground">自动识别：</span>
          <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
            {INPUT_TYPE_LABELS[detected]}
          </span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              type="button"
              disabled={streaming}
              onClick={() => setText(ex.text)}
              className="rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground transition-colors hover:border-emerald-500/40 hover:text-foreground disabled:opacity-50"
            >
              示例：{ex.label}
            </button>
          ))}
        </div>
        <Button size="lg" disabled={streaming || text.trim().length === 0} onClick={() => onAnalyze(text)}>
          {streaming ? <Loader2 className="animate-spin" /> : <Send />}
          {streaming ? "分析中…" : "开始分析"}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 10.3: 结果区**

创建 `frontend/src/components/analysis-result.tsx`：

```tsx
"use client";

import { Check, Copy, Download } from "lucide-react";
import { useState } from "react";

import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";

const DISCLAIMER = "以上内容仅供授权环境下的学习与防御研究使用。";

export function AnalysisResult({ content, streaming }: { content: string; streaming: boolean }) {
  const [copied, setCopied] = useState(false);

  async function copyAll() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // 剪贴板 API 不可用（如非 HTTPS）时静默失败
    }
  }

  function exportMd() {
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `secmate-analysis-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="rounded-xl border border-border bg-card/60 p-5">
      <div className="mb-4 flex items-center justify-between gap-2 border-b border-border pb-3">
        <span className="text-sm font-medium">分析结果</span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={copyAll} disabled={!content}>
            {copied ? <Check className="text-emerald-500" /> : <Copy />}
            {copied ? "已复制" : "复制全文"}
          </Button>
          <Button variant="outline" size="sm" onClick={exportMd} disabled={!content}>
            <Download />
            导出 Markdown
          </Button>
        </div>
      </div>
      {streaming && !content && (
        <div className="space-y-3 py-2">
          <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
          <div className="h-3 w-full animate-pulse rounded bg-muted" />
          <div className="h-3 w-5/6 animate-pulse rounded bg-muted" />
          <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
        </div>
      )}
      {content ? (
        <Markdown content={content} />
      ) : (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {streaming ? "正在生成…" : "分析结果将在这里流式呈现"}
        </p>
      )}
      {content && !streaming && (
        <p className="mt-6 border-t border-border pt-3 text-xs text-muted-foreground">{DISCLAIMER}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 10.4: 分析页状态机**

创建 `frontend/src/components/analyze-client.tsx`：

```tsx
"use client";

import { AlertTriangle, ShieldAlert } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useCallback, useRef, useState } from "react";

import { AnalysisInput } from "@/components/analysis-input";
import { AnalysisResult } from "@/components/analysis-result";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { ApiError, streamAnalysis } from "@/lib/api";
import { isInputType, type InputType } from "@/lib/input-classifier";

type Status = "idle" | "streaming" | "done" | "error";

export function AnalyzeClient() {
  const params = useSearchParams();
  const typeParam = params.get("type");
  const [detectedType, setDetectedType] = useState<InputType | null>(
    isInputType(typeParam) ? typeParam : null,
  );
  const [result, setResult] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleAnalyze = useCallback(
    async (input: string) => {
      setResult("");
      setError(null);
      setStatus("streaming");
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        await streamAnalysis(
          input,
          detectedType,
          {
            onMeta: (t) => setDetectedType(t),
            onDelta: (c) => setResult((prev) => prev + c),
            onDone: () => setStatus("done"),
            onError: (_code, message) => {
              setError(message);
              setStatus("error");
            },
          },
          controller.signal,
        );
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError(err instanceof ApiError ? err.message : "网络错误，请稍后重试");
          setStatus("error");
        }
      }
    },
    [detectedType],
  );

  const handleStop = () => {
    abortRef.current?.abort();
    setStatus("done");
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI 安全分析</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            粘贴报错、HTTP 报文、代码或 CTF 题目，获取七段式学习讲解（流式输出）。
          </p>
        </div>
        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            <ShieldAlert className="mt-0.5 size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}
        <AnalysisInput
          onAnalyze={handleAnalyze}
          streaming={status === "streaming"}
          initialText={params.get("text") ?? ""}
        />
        {(status === "streaming" || status === "done" || result) && (
          <AnalysisResult content={result} streaming={status === "streaming"} />
        )}
        {status === "streaming" && (
          <div className="flex justify-center">
            <Button variant="outline" size="sm" onClick={handleStop}>
              <AlertTriangle />
              停止生成
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}
```

创建 `frontend/src/app/analyze/page.tsx`：

```tsx
import type { Metadata } from "next";
import { Suspense } from "react";

import { AnalyzeClient } from "@/components/analyze-client";

export const metadata: Metadata = {
  title: "AI 安全分析 - SecMate",
  description: "粘贴报错、HTTP 报文、代码或 CTF 题目，获取七段式流式学习讲解。",
};

export default function AnalyzePage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-muted-foreground">加载中…</div>}>
      <AnalyzeClient />
    </Suspense>
  );
}
```

- [ ] **Step 10.5: 构建验证**

Run: `cd frontend && npm run build`
Expected: 构建成功。若 `useSearchParams` 报缺少 Suspense 边界，确认 page.tsx 的 Suspense 包裹无误。

- [ ] **Step 10.6: 提交**

```bash
git add frontend/src/components/site-header.tsx frontend/src/components/analysis-input.tsx frontend/src/components/analysis-result.tsx frontend/src/components/analyze-client.tsx frontend/src/app/analyze/page.tsx
git commit -m "feat(frontend): 分析页——输入/流式渲染/复制导出/停止生成"
```

---

## Task 11: 前端首页（M1）

**Files:**
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 11.1: 重写首页**

将 `frontend/src/app/page.tsx` 完整替换为：

```tsx
import Link from "next/link";
import {
  ArrowRight,
  Braces,
  Bug,
  FileCode2,
  Flag,
  Globe,
  ShieldCheck,
  Terminal,
} from "lucide-react";

import { SiteHeader } from "@/components/site-header";
import { buttonVariants } from "@/components/ui/button";
import { EXAMPLES } from "@/lib/examples";

const FEATURES = [
  { icon: Globe, title: "HTTP 报文分析", desc: "逐行解读请求行、请求头与报文体的结构语义" },
  { icon: Bug, title: "报错信息诊断", desc: "从报错定位根因，讲解背后的信息泄露风险" },
  { icon: Braces, title: "代码安全分析", desc: "发现代码风险点，给出防御写法示例" },
  { icon: Flag, title: "CTF 思路引导", desc: "给方向、讲原理、提示关键点，不直接给答案" },
  { icon: Terminal, title: "Linux 命令解读", desc: "命令意图、参数含义与安全注意点" },
  { icon: FileCode2, title: "网络协议讲解", desc: "TCP / DNS / TLS 等协议原理与常见缺陷" },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] bg-[size:48px_48px] opacity-20 [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,black,transparent)]"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -top-32 left-1/2 h-72 w-[36rem] -translate-x-1/2 rounded-full bg-emerald-500/20 blur-3xl"
        />
        <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-24 text-center sm:pt-32">
          <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
            <ShieldCheck className="size-3.5" />
            AI Powered Cyber Security Learning Assistant
          </div>
          <h1 className="text-5xl font-bold tracking-tight sm:text-7xl">SecMate</h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
            把看不懂的报错、请求、命令、CTF 题目，变成讲得清原理、给得出方向、指得明练习环境的学习材料。
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <Link href="/analyze" className={buttonVariants({ size: "lg", className: "h-11 px-6 text-base" })}>
              开始分析
              <ArrowRight />
            </Link>
            <Link
              href="#features"
              className={buttonVariants({ variant: "outline", size: "lg", className: "h-11 px-6 text-base" })}
            >
              了解特性
            </Link>
          </div>
          <p className="mt-6 text-xs text-muted-foreground">
            每日免费体验 · 无需注册 · 仅支持授权环境（靶场）下的学习与防御研究
          </p>
        </div>
      </section>

      {/* 特性区 */}
      <section id="features" className="mx-auto max-w-6xl px-4 py-16">
        <h2 className="text-center text-2xl font-bold tracking-tight">六类输入，一种解法</h2>
        <p className="mx-auto mt-2 max-w-xl text-center text-sm text-muted-foreground">
          自动识别输入类型，按「七段式」结构化讲解：问题分析 → 原理解释 → 学习方向 → 排查思路 → 修复建议 → 知识点 → 练习环境
        </p>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="rounded-xl border border-border bg-card/60 p-5 transition-colors hover:border-emerald-500/40"
            >
              <div className="flex size-9 items-center justify-center rounded-lg border border-border text-emerald-500">
                <f.icon className="size-4.5" />
              </div>
              <h3 className="mt-3 font-medium">{f.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 示例区 */}
      <section className="mx-auto max-w-6xl px-4 pb-20">
        <h2 className="text-center text-2xl font-bold tracking-tight">先看个例子</h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {EXAMPLES.map((ex) => (
            <Link
              key={ex.label}
              href={`/analyze?type=${ex.type}&text=${encodeURIComponent(ex.text)}`}
              className="group rounded-xl border border-border bg-card/60 p-5 transition-colors hover:border-emerald-500/40"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">{ex.label}</span>
                <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </div>
              <pre className="mt-3 line-clamp-4 overflow-hidden whitespace-pre-wrap break-all font-mono text-xs leading-relaxed text-muted-foreground">
                {ex.text}
              </pre>
            </Link>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-4 py-8 text-center text-xs text-muted-foreground">
          <p>SecMate 仅支持授权环境（靶场）下的学习与防御研究，所有分析结果仅供学习使用。</p>
          <p>© 2026 SecMate · MIT License</p>
        </div>
      </footer>
    </div>
  );
}
```

- [ ] **Step 11.2: 构建验证**

Run: `cd frontend && npm run build`
Expected: 构建成功。若 `line-clamp-4` 未生效（Tailwind v4 已内置 line-clamp 工具类，无需插件）。

- [ ] **Step 11.3: 提交**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat(frontend): 正式首页——Hero/特性区/示例卡/页脚（M1）"
```

---

## Task 12: 端到端验证、部署文档与收尾

**Files:**
- Create: `docs/deploy.md`
- Modify: `README.md`（阶段进度表更新）

- [ ] **Step 12.1: 后端全量测试**

Run: `cd backend && ./.venv/Scripts/python -m pytest -q`
Expected: 全部通过（约 41 个）

- [ ] **Step 12.2: 后端真实运行 + SSE 冒烟（无 Key 时验证错误路径）**

启动（避开被占用的 8000）：

Run: `cd backend && ./.venv/Scripts/python -m uvicorn app.main:app --port 8001 --log-level warning`（后台）

请求：

```
curl -N -X POST http://127.0.0.1:8001/api/v1/analysis \
  -H "Content-Type: application/json" \
  -d '{"input_text":"Traceback (most recent call last):\n  File \"a.py\", line 1, in <module>\nValueError: x"}'
```

Expected（未配置 AI Key）：先 `event: meta`（input_type=error），随后 `event: error`（code=provider_error）。若用户已配置 DeepSeek Key，则为 meta → 连续 delta → done，首 token 应在数秒内到达。

完成后停止后台进程。

- [ ] **Step 12.3: 前端构建 + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: 全部通过

- [ ] **Step 12.4: 浏览器端到端验证（Playwright）**

使用 webapp-testing 技能：前后端 dev server 同时运行（后端 8001、前端 3000，`.env.local` 设置 `BACKEND_API_URL=http://localhost:8000` 时前端默认即可；若用 8001 需在 `.env.local` 覆盖）。

验证清单：
1. 首页渲染：SecMate 标题、英文标语、开始分析按钮、6 张特性卡、3 张示例卡
2. 点击「开始分析」→ 进入 /analyze
3. 点击「示例：报错信息」→ 文本框填充、类型徽标显示「报错信息」
4. 点击「开始分析」→ 结果区出现流式内容（有 Key）或错误提示（无 Key，UI 不崩溃）
5. 结果流结束后「复制全文」「导出 Markdown」可用
6. 首页示例卡点击 → 分析页预填文本
7. 主题切换按钮在明/暗间切换
8. 移动端宽度（375px）布局不破版

- [ ] **Step 12.5: 部署文档**

创建 `docs/deploy.md`：

````markdown
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
````

- [ ] **Step 12.6: README 阶段进度更新**

修改 `README.md`：将阶段3 行标记为「✅ 完成（2026-09-05）」，阶段4 标记为「⏳ 下一阶段」；快速启动一节补充「若 8000 被占用可加 `--port 8001`」。

- [ ] **Step 12.7: 更新项目记忆**

更新 `C:\Users\22145\.qoder-cn\projects\D--ku-VScode-Saas\memory\project-secmate-overview.md`：阶段2+3 已完成、阶段4 待启动；记录 SSE 协议约定（meta/delta/done/error）与「后端为类型识别唯一权威」等关键决策。

- [ ] **Step 12.8: 最终提交**

```bash
git add docs/deploy.md README.md
git commit -m "docs: 部署手册与阶段进度更新（阶段3 完成）"
```

---

## 自审记录

1. **规格覆盖**：M1（Task 11 首页）M2（Task 10 分析页：8000 字符限制、自动识别、流式 Markdown、代码高亮、复制/导出）M3（Task 6 SSE API：七段式由提示词保证、超时与错误处理）M4（Task 6 基于阶段2 Provider 抽象，换环境变量切换）M5（Task 2 安全护栏 + Task 4 红线提示词）M6（Task 3 限流 429）M7（Task 5 落库）M8（Task 12 部署文档+检查清单，真实上线需用户账户配合）。
2. **占位符扫描**：无 TBD/TODO；所有代码步骤含完整代码。
3. **类型一致性**：`InputType` 后端 `Literal` 七值、前端 `InputType` 联合类型一致；SSE 事件名 `meta/delta/done/error` 前后端一致；`record_analysis` 签名在 Task 5/6 间一致。
4. **已知权衡**：限流为单进程内存实现（多实例需换 Redis，阶段后处理）；真实目标检测为启发式（阈值可调，测试锁定当前行为）；示例数据已避免触发自身安全拦截（无 password= 明文）。
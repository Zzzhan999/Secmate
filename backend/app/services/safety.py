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

# ASCII 词需要 \b 避免子串误伤（如 hackthebox）；CJK 词在 Python 中属于 \w，\b 会失效，直接匹配
_ATTACK_VERBS = re.compile(
    r"(?i)\b(?:getshell|exploit|hack|attack|pwn)\b|(?:攻击|入侵|拿下|爆破|渗透|打穿|挂马|肉鸡|远控)"
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

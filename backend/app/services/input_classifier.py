import re
from typing import Literal

InputType = Literal["http", "error", "code", "ctf", "linux", "protocol", "general"]

# 识别顺序即优先级：报文/报错特征强，先匹配；CTF 关键词次之。
_HTTP_LINE = re.compile(r"^(?:GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS|TRACE)\s+\S+\s+HTTP/\d", re.IGNORECASE)
_HTTP_STATUS = re.compile(r"^HTTP/\d(?:\.\d)?\s+\d{3}\b", re.IGNORECASE)
_ERROR = re.compile(
    r"Traceback \(most recent call last\)|Exception in thread|"
    r"\b(?:fatal|syntax|parse|type|value|key|index|runtime|connection)\s*error\b|"
    r"connection\s+refused",
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

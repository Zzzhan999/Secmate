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

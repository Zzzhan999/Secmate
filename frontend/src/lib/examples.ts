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

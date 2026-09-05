import re

_CJK = re.compile(r"[\u4e00-\u9fff]")


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数：CJK 字符按 1 token，其余约 4 字符 1 token。仅用于统计展示，不追求精确。"""
    cjk = len(_CJK.findall(text))
    other = len(text) - cjk
    return max(1, cjk + round(other / 4))

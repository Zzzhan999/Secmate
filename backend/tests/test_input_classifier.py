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

from app.services.tokens import estimate_tokens


def test_cjk_chars_count_as_one_token_each():
    assert estimate_tokens("你好") == 2


def test_latin_chars_grouped_by_four():
    assert estimate_tokens("hello world") == 3  # 11 字符 / 4 ≈ 2.75 → 3


def test_empty_text_returns_at_least_one():
    assert estimate_tokens("") == 1

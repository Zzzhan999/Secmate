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
    import time

    limiter = SlidingWindowLimiter(limit=1, window_seconds=0.01)
    assert limiter.allow("ip-a") is True
    assert limiter.allow("ip-a") is False
    time.sleep(0.02)
    assert limiter.allow("ip-a") is True


def test_remaining_counts_down():
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60.0)
    limiter.allow("ip-a")
    assert limiter.remaining("ip-a") == 1

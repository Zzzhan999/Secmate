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

import logging
import threading
import time
from collections.abc import Iterator

logger = logging.getLogger(__name__)


class LLMUnavailable(Exception):
    """熔断打开或重试耗尽：大模型服务暂时不可用。"""


class CircuitBreaker:
    """连续 N 次失败熔断 M 秒，期间快速失败；窗口过后放行一次探测。"""

    def __init__(self, threshold: int = 5, reset_seconds: int = 300) -> None:
        self.threshold = threshold
        self.reset_seconds = reset_seconds
        self.failures = 0
        self.open_until = 0.0
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self.open_until <= 0:
                return True
            if time.time() < self.open_until:
                return False
            # 熔断窗口结束：半开探测，重置计数
            self.open_until = 0.0
            self.failures = 0
            return True

    def record_success(self) -> None:
        with self._lock:
            self.failures = 0
            self.open_until = 0.0

    def record_failure(self) -> None:
        with self._lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self.open_until = time.time() + self.reset_seconds
                logger.warning(
                    "LLM 熔断打开：连续失败 %d 次，%ds 后放行探测",
                    self.failures,
                    self.reset_seconds,
                )


breaker = CircuitBreaker()

RETRY_TIMES = 2
DEGRADE_MSG = "大模型服务暂时繁忙，请稍后重试"


def stream_with_resilience(provider, messages: list[dict]) -> Iterator[str]:
    """外发前脱敏 + 首包重试 + 熔断计数；失败最终抛 LLMUnavailable。"""
    from app.services.privacy import desensitize_messages

    if not breaker.allow():
        raise LLMUnavailable(DEGRADE_MSG)

    safe_messages = desensitize_messages(messages)
    last_exc: Exception | None = None
    for attempt in range(RETRY_TIMES + 1):
        try:
            gen = provider.stream_chat(safe_messages)
            first = next(gen)
        except StopIteration:
            breaker.record_success()
            return
        except LLMUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("LLM 调用失败（第 %d/%d 次）: %s", attempt + 1, RETRY_TIMES + 1, exc)
            continue
        breaker.record_success()
        yield first
        yield from gen
        return
    breaker.record_failure()
    raise LLMUnavailable(DEGRADE_MSG) from last_exc

import pytest
from app.services.llm.resilience import (
    DEGRADE_MSG,
    LLMUnavailable,
    breaker,
    stream_with_resilience,
)


class FlakyProvider:
    """前 n 次失败，之后成功；记录收到的 messages（用于脱敏断言）。"""

    def __init__(self, fail_times: int = 0):
        self.fail_times = fail_times
        self.calls = 0
        self.seen_messages: list[list[dict]] = []

    def stream_chat(self, messages: list[dict]):
        self.seen_messages.append(messages)
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("simulated outage")
        yield from ["你好，", "以下是科普回答"]


@pytest.fixture(autouse=True)
def _reset_breaker():
    breaker.failures = 0
    breaker.open_until = 0.0
    yield
    breaker.failures = 0
    breaker.open_until = 0.0


def test_retry_recovers_from_transient_failure():
    provider = FlakyProvider(fail_times=1)
    chunks = list(stream_with_resilience(provider, [{"role": "user", "content": "hi"}]))
    assert provider.calls == 2  # 第 1 次失败、第 2 次成功
    assert chunks[0] == "你好，"
    assert breaker.failures == 0


def test_circuit_opens_after_consecutive_failures():
    """连续失败达到阈值 → 熔断打开，后续直接降级不再调用 provider。"""
    for _ in range(breaker.threshold):
        provider = FlakyProvider(fail_times=10**9)
        with pytest.raises(LLMUnavailable):
            list(stream_with_resilience(provider, [{"role": "user", "content": "hi"}]))
    assert breaker.open_until > 0

    cold = FlakyProvider(fail_times=10**9)
    with pytest.raises(LLMUnavailable) as exc:
        list(stream_with_resilience(cold, [{"role": "user", "content": "hi"}]))
    assert DEGRADE_MSG in str(exc.value)
    assert cold.calls == 0  # 熔断期快速失败，未触达 provider


def test_breaker_recovers_after_reset():
    breaker.failures = breaker.threshold
    breaker.open_until = 10**12  # 强制打开
    assert not breaker.allow()
    breaker.open_until = 0.0  # 模拟窗口结束
    breaker.failures = 0
    provider = FlakyProvider()
    chunks = list(stream_with_resilience(provider, [{"role": "user", "content": "hi"}]))
    assert chunks and breaker.failures == 0


def test_outbound_messages_desensitized():
    """外发前脱敏：provider 收到的 content 已去除手机号等敏感信息。"""
    provider = FlakyProvider()
    list(
        stream_with_resilience(provider, [{"role": "user", "content": "我手机号13812345678，头疼"}])
    )
    sent = provider.seen_messages[0][0]["content"]
    assert "13812345678" not in sent
    assert "138****5678" in sent

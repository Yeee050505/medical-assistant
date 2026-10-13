import asyncio

from app.core.gateway import RateLimitMiddleware


def _mw(qps: int = 2, window_ms: int = 1000) -> RateLimitMiddleware:
    return RateLimitMiddleware(None, qps=qps, window_ms=window_ms)


def test_sliding_window_limits_within_window():
    async def run():
        mw = _mw(qps=2)
        key = "itest-window"
        return [
            await mw._allow(key, now=1000.0),
            await mw._allow(key, now=1000.2),
            await mw._allow(key, now=1000.4),
            await mw._allow(key, now=1000.9),
        ]

    assert asyncio.run(run()) == [True, True, False, False]


def test_sliding_window_recovers_after_slide():
    """窗口滑过后（now 前移 > 窗口长度），旧记录过期，重新放行。"""

    async def run():
        mw = _mw(qps=2)
        key = "itest-slide"
        before = [
            await mw._allow(key, now=2000.0),
            await mw._allow(key, now=2000.1),
            await mw._allow(key, now=2000.2),
        ]
        after = [
            await mw._allow(key, now=2001.3),
            await mw._allow(key, now=2001.4),
            await mw._allow(key, now=2001.5),
        ]
        return before, after

    before, after = asyncio.run(run())
    assert before == [True, True, False]
    assert after == [True, True, False]


def test_window_length_is_respected():
    """窗口长度生效：超出窗口的旧请求被清出计数。"""

    async def run():
        mw = _mw(qps=1, window_ms=1000)
        key = "itest-windowlen"
        return [
            await mw._allow(key, now=3000.0),
            await mw._allow(key, now=3000.5),
            await mw._allow(key, now=3001.01),
        ]

    assert asyncio.run(run()) == [True, False, True]

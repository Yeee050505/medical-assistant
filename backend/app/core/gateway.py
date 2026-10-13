import time
import uuid

import redis.asyncio as aioredis
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

EXEMPT_PATHS = {"/api/v1/health"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """网关限流：Redis ZSET 滑动窗口，按登录用户（token sub）或客户端 IP 维度，超限 429。

    相比固定窗口，滑动窗口消除窗口边界的临界突刺（边界处最多放行 2×qps 的问题）。
    """

    def __init__(self, app, qps: int | None = None, window_ms: int | None = None):
        super().__init__(app)
        self.qps = qps if qps is not None else settings.rate_limit_qps
        self.window_ms = window_ms if window_ms is not None else settings.rate_limit_window_ms
        self._redis: aioredis.Redis | None = None

    def _client(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        return self._redis

    def _identity(self, request: Request) -> str:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            try:
                import jwt

                payload = jwt.decode(
                    auth[7:].strip(),
                    settings.jwt_secret,
                    algorithms=[settings.jwt_algorithm],
                    options={"verify_exp": False},
                )
                return f"u{payload.get('sub', '')}"
            except jwt.InvalidTokenError:
                pass
        client_ip = request.client.host if request.client else "unknown"
        return f"ip{client_ip}"

    async def _allow(self, identity: str, now: float | None = None) -> bool:
        """滑动窗口判定：窗口内计数 <= qps 放行。now 可注入（测试窗口滑动）。"""
        now = now if now is not None else time.time()
        key = f"rl:{identity}"
        window_start = now - self.window_ms / 1000
        member = f"{now:.6f}:{uuid.uuid4().hex[:8]}"
        try:
            pipe = self._client().pipeline()
            pipe.zremrangebyscore(key, "-inf", window_start)
            pipe.zadd(key, {member: now})
            pipe.zcard(key)
            pipe.expire(key, max(2, self.window_ms // 1000 + 1))
            results = await pipe.execute()
            count = int(results[2])
        except Exception:  # noqa: BLE001
            return True  # Redis 不可用时放行，避免误伤业务

        if count > self.qps:
            try:
                await self._client().zrem(key, member)  # 超限请求不占坑
            except Exception:  # noqa: BLE001
                pass
            return False
        return True

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        if not await self._allow(self._identity(request)):
            trace_id = getattr(request.state, "trace_id", uuid.uuid4().hex)
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "msg": "请求触发限流",
                    "data": None,
                    "traceId": trace_id,
                },
                headers={"X-Trace-Id": trace_id},
            )
        return await call_next(request)


def install_gateway_middlewares(app: FastAPI) -> None:
    """Python 网关层：限流（先注册，处于内层）+ traceId（后注册，处于最外层）。"""
    from app.core.middleware import TraceMiddleware

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(TraceMiddleware)

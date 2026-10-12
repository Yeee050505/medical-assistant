import time

import redis.asyncio as aioredis
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

EXEMPT_PATHS = {"/api/v1/health"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """网关限流：固定窗口 1s 计数，按登录用户（token sub）或客户端 IP 维度，超限 429。"""

    def __init__(self, app, qps: int | None = None):
        super().__init__(app)
        self.qps = qps or settings.rate_limit_qps
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

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        window = int(time.time())
        key = f"rl:{self._identity(request)}:{window}"
        try:
            r = self._client()
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, 2)
        except Exception:
            count = 0  # Redis 不可用时放行，避免误伤业务

        if count > self.qps:
            import uuid

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

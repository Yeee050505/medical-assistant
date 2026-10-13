import asyncio
import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import trace_id_var
from app.core.metrics import record_http

logger = logging.getLogger("access")

_ID_SEGMENT = re.compile(r"/[0-9a-fA-F-]{16,}|/\d{4,}")


def _route_path(request: Request) -> str:
    """指标标签取路由模板；无模板时归一化 ID/数字段，避免高基数。"""
    route = request.scope.get("route")
    template = getattr(route, "path", "") if route else ""
    if template:
        return template
    return _ID_SEGMENT.sub("/{id}", request.url.path)


class TraceMiddleware(BaseHTTPMiddleware):
    """全链路 traceId：透传或生成，写入 contextvar（日志/指标）与响应头。"""

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        request.state.trace_id = trace_id
        token = trace_id_var.set(trace_id)
        start = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                record_http(
                    request.method,
                    _route_path(request),
                    500,
                    time.perf_counter() - start,
                )
                logger.exception(
                    "unhandled_error trace=%s %s %s cost=%dms",
                    trace_id,
                    request.method,
                    request.url.path,
                    int((time.perf_counter() - start) * 1000),
                )
                raise

            elapsed = time.perf_counter() - start
            record_http(request.method, _route_path(request), response.status_code, elapsed)
            response.headers["X-Trace-Id"] = trace_id
            response.headers["X-Cost-Ms"] = str(int(elapsed * 1000))
            logger.info(
                "access trace=%s %s %s -> %s cost=%dms",
                trace_id,
                request.method,
                request.url.path,
                response.status_code,
                int(elapsed * 1000),
            )
            from app.core.audit import write_audit

            await asyncio.to_thread(
                write_audit,
                trace_id=trace_id,
                method=request.method,
                path=request.url.path,
                code=response.status_code,
                ip=request.client.host if request.client else "",
                cost_ms=int(elapsed * 1000),
                auth_header=request.headers.get("Authorization", ""),
            )
            return response
        finally:
            trace_id_var.reset(token)


def get_trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "")

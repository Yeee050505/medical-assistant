import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("access")


class TraceMiddleware(BaseHTTPMiddleware):
    """全链路 traceId：透传或生成，写入请求状态与响应头。"""

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        request.state.trace_id = trace_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            cost_ms = int((time.perf_counter() - start) * 1000)
            logger.exception(
                "unhandled_error trace=%s %s %s cost=%dms",
                trace_id,
                request.method,
                request.url.path,
                cost_ms,
            )
            raise
        cost_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Cost-Ms"] = str(cost_ms)
        logger.info(
            "access trace=%s %s %s -> %s cost=%dms",
            trace_id,
            request.method,
            request.url.path,
            response.status_code,
            cost_ms,
        )
        return response


def get_trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "")

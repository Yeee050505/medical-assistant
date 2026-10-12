from fastapi import HTTPException, Request, status

from app.core.config import settings


def success(request: Request, data=None, msg: str = "success") -> dict:
    trace_id = getattr(request.state, "trace_id", "")
    return {"code": 200, "msg": msg, "data": data, "traceId": trace_id}


def error_response(code: int, msg: str, http_status: int, trace_id: str = "") -> dict:
    return {"code": code, "msg": msg, "data": None, "traceId": trace_id}


def http_exception_handler(request: Request, exc: HTTPException) -> dict:
    detail = exc.detail if isinstance(exc.detail, str) else "request error"
    trace_id = getattr(request.state, "trace_id", "")
    return error_response(exc.status_code, detail, exc.status_code, trace_id)


def unauthorized(msg: str = "未登录 / token 失效") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=msg)


def forbidden(msg: str = "RBAC 权限拒绝") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg)


def bad_request(msg: str = "参数非法") -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


def not_found(msg: str = "资源不存在") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)


def server_error(msg: str = "服务内部异常") -> HTTPException:
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)


def is_mock() -> bool:
    return settings.llm_provider == "mock"

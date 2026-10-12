import logging

from app.core.database import SessionLocal
from app.models.monitor import AuditLog

logger = logging.getLogger("audit")

AUDIT_EXEMPT_PATHS = {"/api/v1/health"}


def _extract_user_id(auth_header: str) -> int | None:
    if not auth_header.startswith("Bearer "):
        return None
    try:
        import jwt

        from app.core.config import settings

        payload = jwt.decode(
            auth_header[7:].strip(),
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )
        return int(payload.get("sub", 0) or 0)
    except Exception:  # noqa: BLE001
        return None


def write_audit(
    *,
    trace_id: str,
    method: str,
    path: str,
    code: int,
    ip: str,
    cost_ms: int,
    auth_header: str = "",
) -> None:
    if path in AUDIT_EXEMPT_PATHS:
        return
    try:
        with SessionLocal() as db:
            db.add(
                AuditLog(
                    trace_id=trace_id,
                    user_id=_extract_user_id(auth_header),
                    method=method,
                    path=path[:255],
                    code=code,
                    ip=ip[:45],
                    cost_ms=cost_ms,
                )
            )
            db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("写入 audit_log 失败: %s", exc)

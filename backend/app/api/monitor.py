from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.response import bad_request, success
from app.models.monitor import AuditLog, LlmUsage

router = APIRouter()


def _apply_date_range(column, startDate: str, endDate: str, conds: list) -> None:
    for value, op in ((startDate, "start"), (endDate, "end")):
        if not value:
            continue
        try:
            day = datetime.fromisoformat(value)
        except ValueError:
            raise bad_request("日期格式应为 YYYY-MM-DD") from None
        if op == "end":
            day = day + timedelta(days=1)
            conds.append(column < day)
        else:
            conds.append(column >= day)


@router.get("/llm/cost")
def llm_cost(
    request: Request,
    startDate: str = "",
    endDate: str = "",
    user: dict = Depends(require_permission("monitor:admin")),
    db: Session = Depends(get_db),
):
    conds: list = []
    _apply_date_range(LlmUsage.created_at, startDate, endDate, conds)
    row = db.execute(
        select(
            func.count(LlmUsage.id),
            func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
            func.coalesce(func.sum(LlmUsage.completion_tokens), 0),
            func.coalesce(func.sum(LlmUsage.cost), 0),
        ).where(*conds)
    ).one()
    by_type = db.execute(
        select(
            LlmUsage.api_type,
            func.count(LlmUsage.id),
            func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
            func.coalesce(func.sum(LlmUsage.completion_tokens), 0),
        )
        .where(*conds)
        .group_by(LlmUsage.api_type)
    ).all()
    return success(
        request,
        {
            "totalCalls": int(row[0]),
            "totalPromptTokens": int(row[1]),
            "totalCompletionTokens": int(row[2]),
            "totalCost": float(row[3]),
            "byApiType": [
                {
                    "apiType": t,
                    "calls": int(c),
                    "promptTokens": int(pt),
                    "completionTokens": int(ct),
                }
                for t, c, pt, ct in by_type
            ],
            "startDate": startDate,
            "endDate": endDate,
        },
    )


@router.get("/log")
def audit_log(
    request: Request,
    traceId: str = "",
    startDate: str = "",
    endDate: str = "",
    page: int = 1,
    size: int = 20,
    user: dict = Depends(require_permission("monitor:admin")),
    db: Session = Depends(get_db),
):
    page = max(page, 1)
    size = min(max(size, 1), 100)
    conds: list = []
    if traceId.strip():
        conds.append(AuditLog.trace_id == traceId.strip())
    _apply_date_range(AuditLog.created_at, startDate, endDate, conds)
    q = select(AuditLog).where(*conds)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    rows = list(
        db.execute(
            q.order_by(desc(AuditLog.id)).offset((page - 1) * size).limit(size)
        ).scalars()
    )
    items = [
        {
            "traceId": r.trace_id,
            "userId": r.user_id,
            "method": r.method,
            "path": r.path,
            "code": r.code,
            "ip": r.ip,
            "costMs": r.cost_ms,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return success(request, {"list": items, "total": total, "page": page, "size": size})

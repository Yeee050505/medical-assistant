import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select

from app.core.celery_app import celery_app

logger = logging.getLogger("sched")


def _day_window(stat_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(stat_date, time.min)
    return start, start + timedelta(days=1)


@celery_app.task(name="sched.aggregate_daily_usage")
def aggregate_daily_usage(stat_date: str = "") -> dict:
    """每日聚合 llm_usage → llm_usage_daily（幂等 upsert，按 api_type 分组）。"""
    from app.core.database import SessionLocal
    from app.models.monitor import LlmUsage, LlmUsageDaily

    day = date.fromisoformat(stat_date) if stat_date else datetime.now().date() - timedelta(days=1)
    start, end = _day_window(day)

    with SessionLocal() as db:
        rows = db.execute(
            select(
                LlmUsage.api_type,
                func.count(LlmUsage.id),
                func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
                func.coalesce(func.sum(LlmUsage.completion_tokens), 0),
                func.coalesce(func.sum(LlmUsage.cost), 0),
                func.coalesce(func.avg(LlmUsage.duration_ms), 0),
            )
            .where(LlmUsage.created_at >= start, LlmUsage.created_at < end)
            .group_by(LlmUsage.api_type)
        ).all()

        total_calls = 0
        for api_type, calls, pt, ct, cost, avg_ms in rows:
            existing = db.execute(
                select(LlmUsageDaily).where(
                    LlmUsageDaily.stat_date == day,
                    LlmUsageDaily.api_type == api_type,
                )
            ).scalar_one_or_none()
            if existing is None:
                db.add(
                    LlmUsageDaily(
                        stat_date=day,
                        api_type=api_type,
                        calls=int(calls),
                        prompt_tokens=int(pt),
                        completion_tokens=int(ct),
                        cost=Decimal(str(cost)),
                        avg_duration_ms=int(avg_ms),
                    )
                )
            else:
                existing.calls = int(calls)
                existing.prompt_tokens = int(pt)
                existing.completion_tokens = int(ct)
                existing.cost = Decimal(str(cost))
                existing.avg_duration_ms = int(avg_ms)
            total_calls += int(calls)
        db.commit()

    logger.info("每日用量聚合完成 date=%s rows=%d calls=%d", day, len(rows), total_calls)
    return {"date": str(day), "apiTypes": len(rows), "calls": total_calls}


@celery_app.task(name="sched.check_usage_alert")
def check_usage_alert(stat_date: str = "") -> dict:
    """用量告警检测：当日 token 合计超过配额 → 写 audit_log（monitor/log 可检索）。"""
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.models.monitor import LlmUsage, LlmUsageDaily

    quota = settings.llm_daily_token_quota
    if quota <= 0:
        return {"skipped": "quota disabled"}

    day = date.fromisoformat(stat_date) if stat_date else datetime.now().date() - timedelta(days=1)

    with SessionLocal() as db:
        agg = db.execute(
            select(
                func.coalesce(func.sum(LlmUsageDaily.prompt_tokens), 0),
                func.coalesce(func.sum(LlmUsageDaily.completion_tokens), 0),
            ).where(LlmUsageDaily.stat_date == day)
        ).one()
        total_tokens = int(agg[0]) + int(agg[1])

        # 聚合表为空时兜底直接查明细（beat 调度顺序不依赖）
        if total_tokens == 0:
            detail = db.execute(
                select(
                    func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
                    func.coalesce(func.sum(LlmUsage.completion_tokens), 0),
                ).where(
                    LlmUsage.created_at >= _day_window(day)[0],
                    LlmUsage.created_at < _day_window(day)[1],
                )
            ).one()
            total_tokens = int(detail[0]) + int(detail[1])

        if total_tokens > quota:
            logger.warning(
                "LLM 用量超额告警：date=%s tokens=%d quota=%d", day, total_tokens, quota
            )
            from app.models.monitor import AuditLog

            db.add(
                AuditLog(
                    trace_id="",
                    method="ALERT",
                    path=f"llm:daily-quota date={day} tokens={total_tokens} quota={quota}",
                    code=429,
                    ip="scheduler",
                    cost_ms=0,
                )
            )
            db.commit()
            return {"alerted": True, "date": str(day), "tokens": total_tokens, "quota": quota}

    return {"alerted": False, "date": str(day), "tokens": total_tokens, "quota": quota}


@celery_app.task(name="sched.backup_qdrant")
def backup_qdrant_snapshot() -> dict:
    """Qdrant 集合快照备份（保留最近 7 份，旧快照自动清理）。"""
    from app.core.config import settings

    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:  # noqa: BLE001
        logger.warning("qdrant-client 未安装，跳过快照备份: %s", exc)
        return {"skipped": "qdrant-client missing"}

    keep = 7
    try:
        client = QdrantClient(url=settings.qdrant_url, timeout=10)
        raw: Any = client.create_snapshot(collection_name=settings.qdrant_collection) or []
        names = [n for n in (getattr(s, "name", None) for s in raw) if n]
        # 清理旧快照（按名称排序即时间序，保留最新 keep 份）
        all_snaps = [
            s
            for s in (client.list_snapshots(settings.qdrant_collection) or [])
            if getattr(s, "name", None)
        ]
        ordered = sorted(all_snaps, key=lambda s: str(getattr(s, "creation_time", "")))
        for stale in ordered[:-keep]:
            stale_name = getattr(stale, "name", None)
            if stale_name:
                client.delete_snapshot(
                    collection_name=settings.qdrant_collection,
                    snapshot_name=stale_name,
                )
        logger.info(
            "Qdrant 快照备份完成 collection=%s created=%d total=%d",
            settings.qdrant_collection,
            len(names),
            len(all_snaps),
        )
        return {"created": len(names), "total": len(all_snaps)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Qdrant 快照备份失败: %s", exc)
        return {"error": str(exc)[:200]}

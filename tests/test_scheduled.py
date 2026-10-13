from datetime import date, datetime, timedelta
from decimal import Decimal

from app.core.database import SessionLocal
from app.models.monitor import LlmUsage, LlmUsageDaily
from app.tasks.scheduled import aggregate_daily_usage, backup_qdrant_snapshot, check_usage_alert

DAY = (datetime.now().date() - timedelta(days=1)).isoformat()


def _clean() -> None:
    with SessionLocal() as db:
        db.query(LlmUsageDaily).delete()
        db.query(LlmUsage).filter(LlmUsage.trace_id == "itest-sched").delete()
        db.commit()


def _seed_usage(day: str, count: int = 3) -> None:
    ts = datetime.fromisoformat(day) + timedelta(hours=10)
    with SessionLocal() as db:
        for i in range(count):
            db.add(
                LlmUsage(
                    trace_id="itest-sched",
                    user_id=1,
                    api_type="llm",
                    prompt_tokens=100,
                    completion_tokens=50,
                    cost=Decimal("0.01"),
                    duration_ms=200 + i,
                    status="success",
                    created_at=ts,
                )
            )
        db.commit()


def test_aggregate_daily_usage():
    _clean()
    try:
        _seed_usage(DAY, count=3)
        result = aggregate_daily_usage(DAY)
        assert result["calls"] == 3

        with SessionLocal() as db:
            row = (
                db.query(LlmUsageDaily)
                .filter(LlmUsageDaily.stat_date == date.fromisoformat(DAY))
                .first()
            )
            assert row is not None
            assert row.calls == 3
            assert row.prompt_tokens == 300
            assert row.completion_tokens == 150

        # 幂等：重复执行不翻倍
        aggregate_daily_usage(DAY)
        with SessionLocal() as db:
            rows = (
                db.query(LlmUsageDaily)
                .filter(LlmUsageDaily.stat_date == date.fromisoformat(DAY))
                .all()
            )
            assert len(rows) == 1
            assert rows[0].calls == 3
    finally:
        _clean()


def test_usage_alert_skipped_when_quota_disabled(monkeypatch):
    from app.core.config import settings

    _clean()
    monkeypatch.setattr(settings, "llm_daily_token_quota", 0)
    result = check_usage_alert(DAY)
    assert result.get("skipped") == "quota disabled"


def test_usage_alert_writes_audit_when_exceeded(monkeypatch):
    from app.core.config import settings
    from app.models.monitor import AuditLog

    _clean()
    try:
        _seed_usage(DAY, count=2)
        aggregate_daily_usage(DAY)
        monkeypatch.setattr(settings, "llm_daily_token_quota", 100)  # 2*(100+50)=300 > 100
        result = check_usage_alert(DAY)
        assert result["alerted"] is True
        assert result["tokens"] == 300

        with SessionLocal() as db:
            alert = (
                db.query(AuditLog)
                .filter(AuditLog.method == "ALERT", AuditLog.path.contains(DAY))
                .first()
            )
            assert alert is not None
            assert alert.code == 429
    finally:
        _clean()


def test_usage_no_alert_under_quota(monkeypatch):
    from app.core.config import settings

    _clean()
    try:
        _seed_usage(DAY, count=1)
        aggregate_daily_usage(DAY)
        monkeypatch.setattr(settings, "llm_daily_token_quota", 10_000)
        before = db_count_alerts(DAY)
        result = check_usage_alert(DAY)
        assert result["alerted"] is False
        assert db_count_alerts(DAY) == before
    finally:
        _clean()


def db_count_alerts(day: str) -> int:
    from app.models.monitor import AuditLog

    with SessionLocal() as db:
        return (
            db.query(AuditLog)
            .filter(AuditLog.method == "ALERT", AuditLog.path.contains(day))
            .count()
        )


def test_qdrant_snapshot_backup():
    result = backup_qdrant_snapshot()
    assert "error" not in result or not result["error"]


def test_beat_schedule_registered():
    from app.core.celery_app import celery_app

    tasks = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert tasks == {
        "sched.aggregate_daily_usage",
        "sched.check_usage_alert",
        "sched.backup_qdrant",
    }

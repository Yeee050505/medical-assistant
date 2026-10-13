from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "medical",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    imports=["app.tasks.ingest", "app.tasks.scheduled"],
    # beat 定时任务：每日凌晨统计/告警/快照（worker 启动加 -B 内嵌调度器）
    beat_schedule={
        "daily-usage-aggregate": {
            "task": "sched.aggregate_daily_usage",
            "schedule": crontab(hour=1, minute=5),
        },
        "daily-usage-alert": {
            "task": "sched.check_usage_alert",
            "schedule": crontab(hour=1, minute=15),
        },
        "daily-qdrant-snapshot": {
            "task": "sched.backup_qdrant",
            "schedule": crontab(hour=2, minute=0),
        },
    },
)

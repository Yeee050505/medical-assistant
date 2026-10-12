import logging

from sqlalchemy import select

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="rag.ingest_doc")
def ingest_doc_task(doc_id: str, drug_name: str, file_path: str, task_id: str) -> dict:
    """离线入库异步任务：解析 → 切片 → 向量化 → 写 Qdrant，回写任务状态。"""
    from app.core.database import SessionLocal
    from app.models.rag import RagDoc, TaskRecord
    from app.services.rag.ingest import ingest_file

    status = "success"
    error = ""
    chunk_count = 0
    try:
        chunk_count = ingest_file(doc_id, drug_name, file_path)
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        error = str(exc)[:500]
        logger.warning("Celery 入库失败 doc=%s: %s", doc_id, exc)

    try:
        with SessionLocal() as db:
            doc = db.execute(select(RagDoc).where(RagDoc.doc_id == doc_id)).scalar_one_or_none()
            if doc is not None:
                doc.status = status
                doc.error_msg = error
            task = db.execute(
                select(TaskRecord).where(TaskRecord.task_id == task_id)
            ).scalar_one_or_none()
            if task is not None:
                task.status = status
                task.error_msg = error
            db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Celery 回写任务状态失败 doc=%s: %s", doc_id, exc)
        return {"status": status, "error": error}

    return {"status": status, "chunks": chunk_count, "error": error}

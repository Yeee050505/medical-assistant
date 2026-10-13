from pathlib import Path
from tempfile import NamedTemporaryFile

from app.core.database import SessionLocal
from app.models.rag import RagDoc, TaskRecord
from app.tasks.ingest import ingest_doc_task

SPEC = "阿莫西林说明书\n\n【禁忌】对青霉素过敏者禁用。\n\n【适应症】呼吸道感染。"


def _make_doc(task_id: str) -> tuple[str, str]:
    doc_id = f"doc-task-{task_id[-6:]}"
    with NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as f:
        f.write(SPEC)
        path = f.name
    with SessionLocal() as db:
        db.add(
            RagDoc(
                doc_id=doc_id,
                drug_name="阿莫西林-任务测试",
                version="v1",
                file_path=path,
                status="processing",
                enabled=1,
                uploader_id=1,
            )
        )
        db.add(TaskRecord(task_id=task_id, doc_id=doc_id, type="doc_ingest", status="processing"))
        db.commit()
    return doc_id, path


def test_ingest_task_success_updates_status():
    task_id = "task-itest-ok"
    doc_id, path = _make_doc(task_id)
    try:
        result = ingest_doc_task(doc_id, "阿莫西林-任务测试", path, task_id)
        assert result["status"] == "success"
        with SessionLocal() as db:
            doc = db.query(RagDoc).filter(RagDoc.doc_id == doc_id).first()
            task = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
            assert doc.status == "success"
            assert task.status == "success"
    finally:
        Path(path).unlink(missing_ok=True)
        with SessionLocal() as db:
            db.query(RagDoc).filter(RagDoc.doc_id == doc_id).delete()
            db.query(TaskRecord).filter(TaskRecord.task_id == task_id).delete()
            db.commit()


def test_ingest_task_failure_records_error():
    task_id = "task-itest-fail"
    doc_id, path = _make_doc(task_id)
    try:
        result = ingest_doc_task(doc_id, "阿莫西林-任务测试", path + ".missing", task_id)
        assert result["status"] == "failed"
        with SessionLocal() as db:
            doc = db.query(RagDoc).filter(RagDoc.doc_id == doc_id).first()
            task = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
            assert doc.status == "failed"
            assert doc.error_msg
            assert task.status == "failed"
    finally:
        Path(path).unlink(missing_ok=True)
        with SessionLocal() as db:
            db.query(RagDoc).filter(RagDoc.doc_id == doc_id).delete()
            db.query(TaskRecord).filter(TaskRecord.task_id == task_id).delete()
            db.commit()

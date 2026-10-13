import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.deps import require_permission
from app.core.response import bad_request, not_found, success
from app.models.rag import RagDoc, TaskRecord
from app.services.rag import search_chunks
from app.services.rag.ingest import ingest_file, save_upload

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_SUFFIX = {".pdf", ".txt", ".md"}
MAX_DOC_SIZE = 20 * 1024 * 1024


@router.post("/doc/upload")
async def upload_doc(
    request: Request,
    file: UploadFile = File(...),
    drugName: str = Form(...),
    version: str = Form(""),
    user: dict = Depends(require_permission("rag:write")),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIX:
        raise bad_request("文档格式仅支持 pdf/txt/md（错误码 50003）")
    data = await file.read()
    if len(data) > MAX_DOC_SIZE:
        raise bad_request("单文档上限 20MB（错误码 50003）")
    if not drugName.strip():
        raise bad_request("drugName 不能为空")

    doc_id = f"doc-{uuid.uuid4().hex[:16]}"
    task_id = f"task-{uuid.uuid4().hex[:20]}"
    file_path = save_upload(data, doc_id, suffix)

    with SessionLocal() as db:
        db.add(
            RagDoc(
                doc_id=doc_id,
                drug_name=drugName.strip(),
                version=version.strip(),
                file_path=file_path,
                status="processing",
                uploader_id=int(user["sub"]),
            )
        )
        db.add(TaskRecord(task_id=task_id, doc_id=doc_id, type="doc_ingest", status="processing"))
        db.commit()

        status = "success"
        error = ""
        if settings.rag_ingest_async:
            from app.tasks.ingest import ingest_doc_task

            ingest_doc_task.apply_async(
                args=[doc_id, drugName.strip(), file_path, task_id],
                task_id=task_id,
            )
            status = "processing"
        else:
            try:
                ingest_file(doc_id, drugName.strip(), file_path)
            except Exception as exc:  # noqa: BLE001
                status = "failed"
                error = str(exc)[:500]

        row = db.execute(select(RagDoc).where(RagDoc.doc_id == doc_id)).scalar_one()
        row.status = status
        row.error_msg = error
        task = db.execute(select(TaskRecord).where(TaskRecord.task_id == task_id)).scalar_one()
        task.status = status
        task.error_msg = error
        db.commit()

    return success(request, {"docId": doc_id, "taskId": task_id, "status": status})


@router.get("/task/{task_id}")
def get_task(
    task_id: str,
    request: Request,
    user: dict = Depends(require_permission("rag:write")),
    db: Session = Depends(get_db),
):
    task = db.execute(select(TaskRecord).where(TaskRecord.task_id == task_id)).scalar_one_or_none()
    if task is None:
        raise not_found("任务不存在")
    return success(
        request,
        {
            "taskId": task.task_id,
            "docId": task.doc_id,
            "type": task.type,
            "status": task.status,
            "errorMsg": task.error_msg,
        },
    )


@router.get("/doc/list")
def doc_list(
    request: Request,
    user: dict = Depends(require_permission("rag:read")),
    page: int = 1,
    size: int = 10,
    drugName: str = "",
    db: Session = Depends(get_db),
):
    page = max(page, 1)
    size = min(max(size, 1), 50)
    q = select(RagDoc)
    if drugName.strip():
        q = q.where(RagDoc.drug_name.like(f"%{drugName.strip()}%"))
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    rows = list(
        db.execute(
            q.order_by(desc(RagDoc.created_at)).offset((page - 1) * size).limit(size)
        ).scalars()
    )
    items = [
        {
            "docId": r.doc_id,
            "drugName": r.drug_name,
            "version": r.version,
            "status": r.status,
            "enabled": bool(r.enabled),
            "errorMsg": r.error_msg,
            "createdAt": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return success(request, {"list": items, "total": total, "page": page, "size": size})


class DocStatusBody(BaseModel):
    docId: str
    status: str  # enable / disable


@router.put("/doc/status")
def doc_status(
    body: DocStatusBody,
    request: Request,
    user: dict = Depends(require_permission("rag:write")),
    db: Session = Depends(get_db),
):
    if body.status not in {"enable", "disable"}:
        raise bad_request("status 仅支持 enable / disable")
    row = db.execute(select(RagDoc).where(RagDoc.doc_id == body.docId)).scalar_one_or_none()
    if row is None:
        raise not_found("文档不存在")
    enabled = 1 if body.status == "enable" else 0
    row.enabled = enabled
    db.commit()

    from app.services.rag.ingest import invalidate_retrieval
    from app.services.rag.store import set_doc_enabled

    try:
        set_doc_enabled(body.docId, bool(enabled))
    except Exception as exc:  # noqa: BLE001
        logger.warning("同步 Qdrant 启用状态失败 doc=%s: %s", body.docId, exc)
    invalidate_retrieval()
    return success(request, {"docId": row.doc_id, "status": body.status})


class SearchTestBody(BaseModel):
    query: str
    topK: int = 5


@router.post("/search/test")
def search_test(
    body: SearchTestBody,
    request: Request,
    user: dict = Depends(require_permission("rag:read")),
):
    if not body.query.strip():
        raise bad_request("query 不能为空")
    chunks = search_chunks(body.query.strip(), top_k=min(max(body.topK, 1), 20))
    return success(request, {"list": chunks, "total": len(chunks)})

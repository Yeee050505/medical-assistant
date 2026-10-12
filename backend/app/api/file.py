import uuid
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.deps import CurrentUser
from app.core.response import bad_request, success
from app.models.chat import FileObject

router = APIRouter()

ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_SIZE = 10 * 1024 * 1024


@router.post("/upload")
async def upload_file(
    request: Request,
    user: CurrentUser,
    file: UploadFile = File(...),
):
    if file.content_type not in ALLOWED_TYPES:
        raise bad_request("文件类型仅支持 jpg/png/webp（错误码 50003）")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise bad_request("单文件上限 10MB（错误码 50003）")

    file_id = f"file-{uuid.uuid4().hex[:16]}"
    suffix = ALLOWED_TYPES[file.content_type]
    target = Path(settings.upload_dir) / f"{file_id}{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    with SessionLocal() as db:
        db.add(
            FileObject(
                file_id=file_id,
                user_id=int(user["sub"]),
                file_path=str(target),
                mime=file.content_type,
                size_bytes=len(data),
                biz_type="chat",
            )
        )
        db.commit()

    return success(request, {"fileId": file_id, "url": str(target)})

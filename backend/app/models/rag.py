from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RagDoc(Base):
    __tablename__ = "rag_doc"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(String(32), unique=True)
    drug_name: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(32), default="")
    file_path: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="processing")
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    error_msg: Mapped[str] = mapped_column(String(512), default="")
    uploader_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class TaskRecord(Base):
    __tablename__ = "task_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True)
    doc_id: Mapped[str] = mapped_column(String(32), default="")
    type: Mapped[str] = mapped_column(String(32), default="doc_ingest")
    status: Mapped[str] = mapped_column(String(16), default="processing")
    error_msg: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

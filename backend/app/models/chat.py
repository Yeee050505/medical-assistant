from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ChatSession(Base):
    __tablename__ = "chat_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(32), unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    summary: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    reference_docs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FileObject(Base):
    __tablename__ = "file_object"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(String(32), unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    file_path: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(64), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    biz_type: Mapped[str] = mapped_column(String(16), default="chat")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

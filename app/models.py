from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    file_name: Mapped[str] = mapped_column(
        String(255)
    )

    file_type: Mapped[str] = mapped_column(
        String(10)
    )

    file_path: Mapped[str] = mapped_column(
        String(500)
    )

    file_size: Mapped[int] = mapped_column(
        BigInteger
    )

    uploaded_by: Mapped[int | None] = mapped_column(
        Integer
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True
    )


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        Integer
    )

    message: Mapped[str] = mapped_column(
        Text
    )

    response: Mapped[str] = mapped_column(
        Text
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
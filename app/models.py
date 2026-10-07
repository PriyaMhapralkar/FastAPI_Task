from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

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

    uploaded_by: Mapped[str | None] = mapped_column(
        String(255)
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

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)

    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE")
    )

    chunk_index: Mapped[int] = mapped_column(Integer)

    chunk_text: Mapped[str] = mapped_column(Text)

    char_count: Mapped[int] = mapped_column(Integer)

    embedding: Mapped[list[float] | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
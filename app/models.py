from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    file_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True
    )

    file_name: Mapped[str] = mapped_column(
        String(255)
    )

    file_type: Mapped[str] = mapped_column(
        String(10)
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
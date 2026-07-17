from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Prompt(Base):
    __tablename__ = "prompts"
    __table_args__ = (
        Index("ix_prompts_created_at", "created_at"),
        Index("ix_prompts_pending", "processed", "next_attempt_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    original_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

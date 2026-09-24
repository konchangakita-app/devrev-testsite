from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ValidationBase(DeclarativeBase):
    pass


class CrawlValidationRun(ValidationBase):
    """Web Crawler 検証用の実行単位ごとのページ状態（Vercel でも永続化）。"""

    __tablename__ = "crawl_validation_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    for_404_is_gone: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    unlink_for_unlink: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    redirect_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    redirect_target: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

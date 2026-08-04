"""Neon / SQLite 上のアプリ設定（SECRET_KEY 等）。"""

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ConfigBase(DeclarativeBase):
    pass


class AppConfig(ConfigBase):
    """スコープ別の設定値。SECRET_KEY は scope ごとに Neon で管理する。"""

    __tablename__ = "app_config"
    __table_args__ = (UniqueConstraint("scope", "key", name="uq_app_config_scope_key"),)

    scope: Mapped[str] = mapped_column(String(32), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

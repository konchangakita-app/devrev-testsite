from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    devrev_revuser_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # PetStore 互換 API 用（/api/admin/user など）
    api_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True, index=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Reservation(Base):
    """レストラン予約（PMS / SoT）。Neon Postgres または SQLite に永続化。"""

    __tablename__ = "reservations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    visit_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    time_slot: Mapped[str] = mapped_column(String(8), nullable=False)
    meal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    seat_type: Mapped[str] = mapped_column(String(16), nullable=False)
    course: Mapped[str] = mapped_column(String(32), nullable=False)
    guest_name: Mapped[str] = mapped_column(String(80), nullable=False)
    guest_email: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="confirmed")
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

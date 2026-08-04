"""予約 CRUD（PMS / SoT — Neon Postgres または SQLite）。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from helpsite.models import Reservation

STATUS_LABELS = {
    "confirmed": "確定",
    "visited": "来店済み",
    "cancelled": "キャンセル",
}

MEAL_LABELS = {"lunch": "ランチ", "dinner": "ディナー"}
SEAT_LABELS = {"table": "テーブル席", "private": "個室"}
COURSE_LABELS = {
    "kon-standard": "KON スタンダードコース",
    "kon-season": "KON 季節コース",
    "chef-omakase": "シェフおまかせコース",
}

# init_db.py でシードするデモ予約（id 固定）
DEMO_RESERVATION_SEEDS: list[dict[str, Any]] = [
    {
        "id": "KON-20260705-1001",
        "visit_date": "2026-07-05",
        "time_slot": "18:00",
        "meal_type": "dinner",
        "party_size": 2,
        "seat_type": "table",
        "course": "kon-season",
        "guest_name": "田中 花子",
        "guest_email": "hanako@example.com",
        "status": "confirmed",
        "notes": "窓際希望",
    },
    {
        "id": "KON-20260708-1002",
        "visit_date": "2026-07-08",
        "time_slot": "12:00",
        "meal_type": "lunch",
        "party_size": 4,
        "seat_type": "private",
        "course": "chef-omakase",
        "guest_name": "鈴木 一郎",
        "guest_email": "ichiro@example.com",
        "status": "confirmed",
        "notes": "",
    },
    {
        "id": "KON-20260628-1003",
        "visit_date": "2026-06-28",
        "time_slot": "19:00",
        "meal_type": "dinner",
        "party_size": 3,
        "seat_type": "table",
        "course": "kon-standard",
        "guest_name": "佐藤 美咲",
        "guest_email": "misaki@example.com",
        "status": "visited",
        "notes": "",
    },
    {
        "id": "KON-20260712-1004",
        "visit_date": "2026-07-12",
        "time_slot": "11:30",
        "meal_type": "lunch",
        "party_size": 2,
        "seat_type": "table",
        "course": "kon-season",
        "guest_name": "山本 健",
        "guest_email": "ken@example.com",
        "status": "cancelled",
        "notes": "体調不良のため",
    },
    {
        "id": "KON-20260720-1005",
        "visit_date": "2026-07-20",
        "time_slot": "18:00",
        "meal_type": "dinner",
        "party_size": 2,
        "seat_type": "table",
        "course": "kon-season",
        "guest_name": "demo",
        "guest_email": "demo+mbr@helpsite.local",
        "status": "confirmed",
        "notes": "",
    },
]


def _serialize(row: Reservation) -> dict[str, Any]:
    created = row.created_at.strftime("%Y-%m-%d %H:%M") if row.created_at else ""
    return {
        "id": row.id,
        "visit_date": row.visit_date,
        "time_slot": row.time_slot,
        "meal_type": row.meal_type,
        "party_size": row.party_size,
        "seat_type": row.seat_type,
        "course": row.course,
        "guest_name": row.guest_name,
        "guest_email": row.guest_email,
        "status": row.status,
        "notes": row.notes or "",
        "created_at": created,
        "meal_label": MEAL_LABELS.get(row.meal_type, row.meal_type),
        "seat_label": SEAT_LABELS.get(row.seat_type, row.seat_type),
        "course_label": COURSE_LABELS.get(row.course, row.course),
        "status_label": STATUS_LABELS.get(row.status, row.status),
    }


def _query_ordered(db: Session):
    return db.scalars(
        select(Reservation).order_by(Reservation.visit_date.desc(), Reservation.time_slot.desc())
    ).all()


def list_reservations(db: Session) -> list[dict[str, Any]]:
    return [_serialize(row) for row in _query_ordered(db)]


def list_reservations_for_user(db: Session, guest_email: str) -> list[dict[str, Any]]:
    email = guest_email.strip().lower()
    rows = [
        row
        for row in _query_ordered(db)
        if row.guest_email.strip().lower() == email
    ]
    return [_serialize(row) for row in rows]


def cancel_reservation_for_user(db: Session, reservation_id: str, guest_email: str) -> bool:
    email = guest_email.strip().lower()
    row = db.get(Reservation, reservation_id)
    if not row or row.guest_email.strip().lower() != email or row.status != "confirmed":
        return False
    row.status = "cancelled"
    db.commit()
    return True


def _next_id(db: Session, visit_date: str) -> str:
    compact = visit_date.replace("-", "")
    prefix = f"KON-{compact}-"
    existing = db.scalars(
        select(Reservation.id).where(Reservation.id.like(f"{prefix}%"))
    ).all()
    nums: list[int] = []
    for rid in existing:
        try:
            nums.append(int(str(rid).rsplit("-", 1)[-1]))
        except ValueError:
            continue
    n = max(nums, default=1000) + 1
    return f"{prefix}{n}"


def add_reservation(
    db: Session,
    *,
    visit_date: str,
    time_slot: str,
    meal_type: str,
    party_size: int,
    seat_type: str,
    course: str,
    guest_name: str,
    guest_email: str,
    notes: str = "",
) -> dict[str, Any]:
    row = Reservation(
        id=_next_id(db, visit_date),
        visit_date=visit_date,
        time_slot=time_slot,
        meal_type=meal_type,
        party_size=party_size,
        seat_type=seat_type,
        course=course,
        guest_name=guest_name,
        guest_email=guest_email,
        status="confirmed",
        notes=notes.strip(),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize(row)


def update_status(db: Session, reservation_id: str, status: str) -> bool:
    if status not in STATUS_LABELS:
        return False
    row = db.get(Reservation, reservation_id)
    if not row:
        return False
    row.status = status
    db.commit()
    return True


def min_visit_date() -> str:
    return date.today().isoformat()

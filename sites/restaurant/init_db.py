#!/usr/bin/env python3
"""Create schema, migrate legacy SQLite columns, seed demo data (idempotent)."""

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from helpsite.api_keys import generate_api_key
from helpsite.config import INSTANCE_DIR, is_sqlite_database
from helpsite.database import SessionLocal, engine
from helpsite.models import Base, Reservation, User
from helpsite.reservations_demo import DEMO_RESERVATION_SEEDS
from shared.gate.models import Base as GateBase
from werkzeug.security import generate_password_hash

DEMO_MEMBER_USERNAME = "demo"
DEMO_MEMBER_EMAIL = "demo+mbr@helpsite.local"
DEMO_MEMBER_PASSWORD = "demo1234"

DEMO_ADMIN_USERNAME = "konadmin"
DEMO_ADMIN_EMAIL = "konadmin+admin@helpsite.local"
DEMO_ADMIN_PASSWORD = "konadmin1234"


def migrate_sqlite_schema() -> None:
    """既存 SQLite DB に api_key / is_admin 列が無い場合のみ ALTER。"""
    if not is_sqlite_database():
        return
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    with engine.begin() as conn:
        if "api_key" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN api_key VARCHAR(128)"))
        if "is_admin" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"))


def _ensure_api_key(db: Session, user: User) -> bool:
    if user.api_key:
        return False
    user.api_key = generate_api_key()
    return True


def backfill_demo_member(db: Session) -> None:
    """一般会員 demo: 管理者権限は付けない。"""
    demo = db.scalars(select(User).where(User.username == DEMO_MEMBER_USERNAME)).first()
    if not demo:
        return
    changed = False
    if _ensure_api_key(db, demo):
        changed = True
    if demo.is_admin:
        demo.is_admin = False
        changed = True
    if demo.email == "demo@helpsite.local":
        demo.email = DEMO_MEMBER_EMAIL
        changed = True
    if changed:
        db.commit()


def backfill_demo_admin(db: Session) -> None:
    admin = db.scalars(select(User).where(User.username == DEMO_ADMIN_USERNAME)).first()
    if not admin:
        return
    changed = False
    if _ensure_api_key(db, admin):
        changed = True
    if not admin.is_admin:
        admin.is_admin = True
        changed = True
    if changed:
        db.commit()


def seed_users(db: Session) -> None:
    if not db.scalars(select(User).where(User.username == DEMO_MEMBER_USERNAME)).first():
        db.add(
            User(
                username=DEMO_MEMBER_USERNAME,
                email=DEMO_MEMBER_EMAIL,
                password_hash=generate_password_hash(DEMO_MEMBER_PASSWORD, method="pbkdf2:sha256"),
                api_key=generate_api_key(),
                is_admin=False,
            )
        )
        db.commit()
    else:
        backfill_demo_member(db)

    if not db.scalars(select(User).where(User.username == DEMO_ADMIN_USERNAME)).first():
        db.add(
            User(
                username=DEMO_ADMIN_USERNAME,
                email=DEMO_ADMIN_EMAIL,
                password_hash=generate_password_hash(DEMO_ADMIN_PASSWORD, method="pbkdf2:sha256"),
                api_key=generate_api_key(),
                is_admin=True,
            )
        )
        db.commit()
    else:
        backfill_demo_admin(db)


def seed_reservations(db: Session) -> None:
    for seed in DEMO_RESERVATION_SEEDS:
        if db.get(Reservation, seed["id"]):
            continue
        db.add(
            Reservation(
                id=seed["id"],
                visit_date=seed["visit_date"],
                time_slot=seed["time_slot"],
                meal_type=seed["meal_type"],
                party_size=seed["party_size"],
                seat_type=seed["seat_type"],
                course=seed["course"],
                guest_name=seed["guest_name"],
                guest_email=seed["guest_email"],
                status=seed["status"],
                notes=seed.get("notes", ""),
            )
        )
    db.commit()


def main() -> None:
    if is_sqlite_database():
        INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    GateBase.metadata.create_all(bind=engine)
    migrate_sqlite_schema()
    db = SessionLocal()
    try:
        seed_users(db)
        seed_reservations(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()

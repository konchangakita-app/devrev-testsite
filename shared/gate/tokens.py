import secrets
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode, urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.gate.models import DemoInviteToken

INVITE_QUERY_PARAM = "invite"


def generate_token_value() -> str:
    return secrets.token_urlsafe(32)


def create_invite_token(db: Session, label: Optional[str] = None) -> DemoInviteToken:
    for _ in range(10):
        value = generate_token_value()
        exists = db.scalars(select(DemoInviteToken).where(DemoInviteToken.token == value)).first()
        if not exists:
            row = DemoInviteToken(token=value, label=(label or "").strip() or None)
            db.add(row)
            db.commit()
            db.refresh(row)
            return row
    raise RuntimeError("Could not allocate invite token")


def get_token_by_value(db: Session, token_value: str) -> Optional[DemoInviteToken]:
    return db.scalars(select(DemoInviteToken).where(DemoInviteToken.token == token_value)).first()


def get_token_by_id(db: Session, token_id: int) -> Optional[DemoInviteToken]:
    return db.get(DemoInviteToken, token_id)


def list_invite_tokens(db: Session, include_revoked: bool = False) -> list[DemoInviteToken]:
    rows = db.scalars(select(DemoInviteToken).order_by(DemoInviteToken.id.desc())).all()
    if include_revoked:
        return list(rows)
    return [row for row in rows if row.is_active]


def revoke_invite_token(db: Session, token: DemoInviteToken) -> DemoInviteToken:
    if not token.revoked_at:
        token.revoked_at = datetime.utcnow()
        db.commit()
        db.refresh(token)
    return token


def touch_token_used(db: Session, token: DemoInviteToken) -> None:
    token.last_used_at = datetime.utcnow()
    db.commit()


def is_token_usable(token: Optional[DemoInviteToken]) -> bool:
    return token is not None and token.is_active


def build_invite_url(base_url: str, token_value: str, path: str = "/") -> str:
    base = (base_url or "").rstrip("/")
    path = path if path.startswith("/") else f"/{path}"
    return f"{base}{path}?{INVITE_QUERY_PARAM}={token_value}"


def strip_invite_query(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.query:
        return url
    pairs = []
    for part in parsed.query.split("&"):
        if not part:
            continue
        key = part.split("=", 1)[0]
        if key == INVITE_QUERY_PARAM:
            continue
        pairs.append(part)
    new_query = "&".join(pairs)
    return urlunparse(parsed._replace(query=new_query))

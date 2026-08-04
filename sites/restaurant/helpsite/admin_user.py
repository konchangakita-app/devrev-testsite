"""
PetStore 互換: GET /api/admin/user?devrev_revuser_id=...
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from helpsite.config import get_settings
from helpsite.database import get_db
from helpsite.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])


def _strip_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    if authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return authorization.strip()


@router.get("/admin/user")
def get_user_by_devrev_id(
    devrev_revuser_id: Optional[str] = None,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> dict:
    """
    DevRev RevUser ID で PetStore ユーザーを1件取得（認可は PetStore と同様のルール）。
    """
    logger.info("GET /api/admin/user devrev_revuser_id=%s", devrev_revuser_id)

    auth_token = _strip_bearer(authorization)
    if not auth_token:
        raise HTTPException(status_code=401, detail="Authorization header required")

    if not devrev_revuser_id or not devrev_revuser_id.strip():
        raise HTTPException(status_code=400, detail="devrev_revuser_id parameter is required")

    devrev_revuser_id = devrev_revuser_id.strip()

    target_user = db.scalars(
        select(User).where(User.devrev_revuser_id == devrev_revuser_id)
    ).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    settings = get_settings()
    admin_key = (settings.admin_api_key or "").strip()

    if auth_token.startswith("ps"):
        is_admin_access = False
        authenticated_user: Optional[User] = None

        if admin_key and auth_token == admin_key:
            is_admin_access = True
        else:
            authenticated_user = db.scalars(
                select(User).where(User.api_key == auth_token)
            ).first()
            if not authenticated_user:
                raise HTTPException(status_code=401, detail="Invalid API key")
            is_admin_access = bool(authenticated_user.is_admin)

        if is_admin_access:
            pass
        elif authenticated_user and authenticated_user.id == target_user.id:
            pass
        else:
            raise HTTPException(
                status_code=403,
                detail="Forbidden - can only view your own profile",
            )

    elif auth_token.startswith("ey"):
        # PetStore: target の AAT と一致。helpsite はユーザーごと AAT 未保持のため、
        # 環境変数 DEVREV_APPLICATION_ACCESS_TOKEN と一致する場合に許可（組織トークン想定デモ）。
        org_aat = (settings.devrev_application_access_token or "").strip()
        if not org_aat or auth_token.strip() != org_aat:
            raise HTTPException(status_code=401, detail="Invalid AAT for this user")
    else:
        raise HTTPException(
            status_code=401,
            detail="Invalid token format",
        )

    user_data = {
        "id": target_user.id,
        "username": target_user.username,
        "email": target_user.email,
        "first_name": None,
        "last_name": None,
        "phone": None,
        "address": None,
        "devrev_revuser_id": target_user.devrev_revuser_id,
        "is_admin": target_user.is_admin,
        "email_confirmed": True,
        "created_at": target_user.created_at.isoformat() if target_user.created_at else None,
        "last_login": None,
        "use_global_devrev_config": False,
    }
    return {"user": user_data}

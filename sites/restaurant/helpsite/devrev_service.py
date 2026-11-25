import base64
import binascii
import json
import logging
import re
import time
from typing import Optional

import httpx

from helpsite.config import Settings, resolved_application_access_token, resolved_plug_app_id
from helpsite.models import User

logger = logging.getLogger(__name__)

AUTH_TOKENS_URL = "https://api.devrev.ai/auth-tokens.create"
ORG_SHARD_RE = re.compile(r"(dvrv-[a-z]+-\d+)", re.IGNORECASE)

REQUESTED_TOKEN_TYPES = {
    "session": "urn:devrev:params:oauth:token-type:session",
    "session_rev_public": "urn:devrev:params:oauth:token-type:session:rev:public",
}


def extract_org_shard(text: str) -> Optional[str]:
    """DevRev の don / JWT 文字列から org shard（例: dvrv-jp-1）を抽出する。"""
    if not text:
        return None
    m = ORG_SHARD_RE.search(text)
    return m.group(1).lower() if m else None


def org_shard_from_plug_app_id(plug_app_id: str) -> Optional[str]:
    """PLuG app_id（平文 don:… または DvRv 付き Base64）から org shard を得る。"""
    raw = (plug_app_id or "").strip()
    if not raw:
        return None
    shard = extract_org_shard(raw)
    if shard:
        return shard
    # DevRev の DvRv ラップ app_id 内に base64 化された org shard が埋め込まれている（例: ZHZydi1qcC0x → dvrv-jp-1）
    for m in re.finditer(r"ZHZydi[a-zA-Z0-9+/=]+", raw, re.IGNORECASE):
        chunk = m.group(0)
        for end in range(len(chunk), 8, -1):
            part = chunk[:end]
            pad = "=" * ((4 - len(part) % 4) % 4)
            try:
                decoded = base64.b64decode(part + pad).decode("utf-8")
            except (ValueError, binascii.Error, UnicodeDecodeError):
                continue
            shard = extract_org_shard(decoded)
            if shard:
                return shard
    if not raw.startswith("DvRv"):
        return None
    inner = raw[4:]
    eq = inner.find("==")
    if eq >= 0:
        inner = inner[: eq + 2]
    try:
        decoded = base64.b64decode(inner).decode("utf-8", errors="replace")
    except (ValueError, binascii.Error):
        return None
    return extract_org_shard(decoded)


def _session_claims(token: str) -> dict:
    raw = token.strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    parts = raw.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, UnicodeDecodeError):
        return {}
    return claims if isinstance(claims, dict) else {}


def org_shard_from_jwt(token: str) -> Optional[str]:
    claims = _session_claims(token)
    for key in ("azp", "sub", "http://devrev.ai/devo_don", "http://devrev.ai/svcacc"):
        shard = extract_org_shard(str(claims.get(key, "")))
        if shard:
            return shard
    return extract_org_shard(json.dumps(claims)) or extract_org_shard(token)


def plug_org_matches_jwt(plug_app_id: str, jwt_token: str) -> bool:
    """PLuG app_id と JWT の org が一致するか。どちらかが判別不能なら許可（後方互換）。"""
    plug_shard = org_shard_from_plug_app_id(plug_app_id)
    token_shard = org_shard_from_jwt(jwt_token)
    if plug_shard and token_shard:
        return plug_shard == token_shard
    return True


def session_token_valid_for_plug(session_token: str, plug_app_id: str) -> bool:
    expiry = _session_claims(session_token).get("exp")
    return (
        isinstance(expiry, (int, float))
        and expiry > time.time() + 30
        and plug_org_matches_jwt(plug_app_id, session_token)
    )


def _authorization_bearer(token: str) -> str:
    """DevRev API は Authorization: Bearer <token> を要求する。生の JWT のみの場合は付与する。"""
    t = token.strip()
    if t.lower().startswith("bearer "):
        return t
    return f"Bearer {t}"


def _resolved_requested_token_type(settings: Settings) -> str:
    key = (settings.devrev_plug_requested_token_type or "session").strip().lower()
    return REQUESTED_TOKEN_TYPES.get(key, REQUESTED_TOKEN_TYPES["session"])


def _build_user_ref(user: User, settings: Settings) -> str:
    """DevRev の user_ref。既定は mbr:{id}。verified 調査時は email モード可。"""
    mode = (settings.devrev_plug_user_ref or "member_id").strip().lower()
    email = (user.email or "").strip()
    if mode == "email" and email:
        return email
    if user.id is not None:
        return f"mbr:{user.id}"
    if user.username:
        return f"mbr:username:{user.username}"
    return email or "mbr:unknown"


def request_plug_session_token_for_ref(
    user_ref: str,
    settings: Settings,
    *,
    email: str = "",
    display_name: str = "Guest",
    existing_email_ref: str = "",
) -> Optional[str]:
    """任意 user_ref 向け PLuG session token（匿名 PLuG 連携用）。"""
    aat = resolved_application_access_token()
    if not aat:
        return None

    plug_app_id = resolved_plug_app_id()
    if plug_app_id and not plug_org_matches_jwt(plug_app_id, aat):
        logger.warning(
            "DevRev AAT org (%s) does not match PLuG app_id org (%s); skipping auth-tokens.create",
            org_shard_from_jwt(aat),
            org_shard_from_plug_app_id(plug_app_id),
        )
        return None

    rev_info: dict = {
        "user_ref": user_ref,
        "user_traits": {
            "email": email or "",
            "display_name": display_name,
            "phone_numbers": [],
        },
    }
    acc = (settings.devrev_account_ref or "").strip()
    ws = (settings.devrev_workspace_ref or "").strip()
    if acc:
        rev_info["account_ref"] = acc
    if ws:
        rev_info["workspace_ref"] = ws
    payload = {
        "requested_token_type": _resolved_requested_token_type(settings),
        "rev_info": rev_info,
    }
    headers = {
        "Authorization": _authorization_bearer(aat),
        "content-type": "application/json",
        "accept": "application/json",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(AUTH_TOKENS_URL, headers=headers, json=payload)
            if r.status_code == 409 and existing_email_ref and existing_email_ref != user_ref:
                # Reuse the legacy reference without updating the contact's traits or associations.
                payload["rev_info"] = {"user_ref": existing_email_ref}
                r = client.post(AUTH_TOKENS_URL, headers=headers, json=payload)
    except httpx.HTTPError as e:
        logger.warning("DevRev auth-tokens.create request failed: %s", e)
        return None

    if r.status_code not in (200, 201):
        logger.warning(
            "DevRev auth-tokens.create error %s",
            r.status_code,
        )
        return None

    session_token = r.json().get("access_token")
    if not session_token:
        logger.warning("DevRev auth-tokens.create: no access_token in response")
        return None

    if plug_app_id and not plug_org_matches_jwt(plug_app_id, session_token):
        logger.warning("DevRev session token org mismatch; discarding token")
        return None

    return session_token


def request_plug_session_token(user: User, settings: Settings) -> Optional[str]:
    """
    Call DevRev auth-tokens.create using org-level AAT from settings.
    Returns session token (JWT string) for PLuG, or None if AAT missing / API error.
    """
    known_subject = user.devrev_revuser_id
    session_token = request_plug_session_token_for_ref(
        _build_user_ref(user, settings),
        settings,
        email=user.email,
        display_name=user.username,
        existing_email_ref=user.email.strip() if known_subject else "",
    )
    if not session_token:
        return None

    subject = _session_claims(session_token).get("sub")
    if not isinstance(subject, str) or "revu/" not in subject:
        logger.warning("DevRev session token is missing a RevUser subject")
        return None
    if known_subject and subject != known_subject:
        logger.warning("DevRev session token subject does not match the linked RevUser")
        return None

    user.devrev_revuser_id = subject
    return session_token

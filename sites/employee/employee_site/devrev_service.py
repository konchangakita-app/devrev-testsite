import base64
import binascii
import json
import logging
import re
from typing import Optional

import httpx

from employee_site.config import Settings, resolved_application_access_token, resolved_plug_app_id
from employee_site.employees import Employee

logger = logging.getLogger(__name__)

AUTH_TOKENS_URL = "https://api.devrev.ai/auth-tokens.create"
ORG_SHARD_RE = re.compile(r"(dvrv-[a-z]+-\d+)", re.IGNORECASE)


def extract_org_shard(text: str) -> Optional[str]:
    if not text:
        return None
    m = ORG_SHARD_RE.search(text)
    return m.group(1).lower() if m else None


def org_shard_from_plug_app_id(plug_app_id: str) -> Optional[str]:
    raw = (plug_app_id or "").strip()
    if not raw:
        return None
    shard = extract_org_shard(raw)
    if shard:
        return shard
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


def org_shard_from_jwt(token: str) -> Optional[str]:
    raw = (token or "").strip()
    if raw.lower().startswith("bearer "):
        raw = raw[7:].strip()
    parts = raw.split(".")
    if len(parts) != 3:
        return extract_org_shard(raw)
    try:
        payload_b64 = parts[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        pl = json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return extract_org_shard(raw)
    for key in ("azp", "sub", "http://devrev.ai/devo_don", "http://devrev.ai/svcacc"):
        shard = extract_org_shard(str(pl.get(key, "")))
        if shard:
            return shard
    return extract_org_shard(json.dumps(pl))


def plug_org_matches_jwt(plug_app_id: str, jwt_token: str) -> bool:
    plug_shard = org_shard_from_plug_app_id(plug_app_id)
    token_shard = org_shard_from_jwt(jwt_token)
    if plug_shard and token_shard:
        return plug_shard == token_shard
    return True


def session_token_valid_for_plug(session_token: str, plug_app_id: str) -> bool:
    return plug_org_matches_jwt(plug_app_id, session_token)


def _authorization_bearer(token: str) -> str:
    t = token.strip()
    if t.lower().startswith("bearer "):
        return t
    return f"Bearer {t}"


def _build_user_ref(employee: Employee) -> str:
    return f"emp:{employee.employee_id}"


def request_plug_session_token_for_ref(
    user_ref: str,
    settings: Settings,
    *,
    email: str = "",
    display_name: str = "Guest",
) -> Optional[str]:
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
        "requested_token_type": "urn:devrev:params:oauth:token-type:session",
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
    except httpx.HTTPError as e:
        logger.warning("DevRev auth-tokens.create request failed: %s", e)
        return None

    if r.status_code not in (200, 201):
        logger.warning("DevRev auth-tokens.create error %s: %s", r.status_code, r.text[:500])
        return None

    session_token = r.json().get("access_token")
    if not session_token:
        logger.warning("DevRev auth-tokens.create: no access_token in response")
        return None

    if plug_app_id and not plug_org_matches_jwt(plug_app_id, session_token):
        logger.warning("DevRev session token org mismatch; discarding token")
        return None

    return session_token


def request_plug_session_token(employee: Employee, settings: Settings) -> Optional[str]:
    return request_plug_session_token_for_ref(
        _build_user_ref(employee),
        settings,
        email=employee.email,
        display_name=employee.display_name,
    )

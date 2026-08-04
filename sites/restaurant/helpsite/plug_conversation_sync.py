"""会話の custom_fields を DevRev conversations.update で書く（ヘルプサイトのバックエンド経由）。

人間の認識は user_ip。Conversation カスタムフィールドの API 名は tnt__ 接頭辞付き（例: tnt__user_ip）になりやすい。
"""

import json
import logging
import re
from typing import Any, Optional

import httpx

from helpsite.config import Settings, resolved_application_access_token, resolved_devrev_pat

logger = logging.getLogger(__name__)

CONVERSATIONS_UPDATE_URL = "https://api.devrev.ai/conversations.update"
CONVERSATIONS_GET_URL = "https://api.devrev.ai/conversations.get"


def _bearer_token(settings: Settings) -> Optional[str]:
    """専用 PAT があれば優先。なければ Application Access Token（権限が足りる場合のみ成功）。"""
    pat = resolved_devrev_pat()
    if pat:
        return pat
    return resolved_application_access_token()


def _authorization_header(token: str) -> str:
    t = token.strip()
    if t.lower().startswith("bearer "):
        return t
    return f"Bearer {t}"


def _conversation_display_id_from_don(conversation_id: str) -> Optional[str]:
    """
    don:...:conversation/79 → CONV-79。conversations.update の id に display_id を要求するテナント向け。
    """
    raw = conversation_id.strip()
    if not raw.startswith("don:"):
        return None
    m = re.search(r":conversation/(\d+)$", raw)
    if not m:
        return None
    return f"CONV-{m.group(1)}"


def _custom_field_keys_for_ip(settings: Settings) -> list[str]:
    """設定の API 名に加え、もう一方の慣用キーを併試（tnt__user_ip ↔ user_ip）。"""
    primary = (settings.devrev_conversation_custom_field_user_ip or "tnt__user_ip").strip() or "tnt__user_ip"
    keys = [primary]
    if primary == "user_ip" and "tnt__user_ip" not in keys:
        keys.append("tnt__user_ip")
    if primary == "tnt__user_ip" and "user_ip" not in keys:
        keys.append("user_ip")
    return keys


def _conversation_update_body(
    settings: Settings,
    conversation_id: str,
    user_ip: str,
    *,
    custom_field_key: Optional[str] = None,
) -> dict[str, Any]:
    key = (
        custom_field_key
        if custom_field_key is not None
        else (settings.devrev_conversation_custom_field_user_ip or "tnt__user_ip").strip() or "tnt__user_ip"
    )
    body: dict[str, Any] = {
        "id": conversation_id.strip(),
        "custom_fields": {key: user_ip},
    }
    if settings.devrev_conversation_update_send_schema_spec:
        body["custom_schema_spec"] = {
            "tenant_fragment": settings.devrev_conversation_update_tenant_fragment,
            "validate_required_fields": settings.devrev_conversation_update_validate_required_fields,
        }
    return body


def _conversation_update_body_variants(
    settings: Settings,
    conversation_id: str,
    user_ip: str,
) -> list[tuple[str, dict[str, Any]]]:
    """
    DevOrg によって有効な custom_schema_spec / custom_fields のキーが違うため、重複のない body を順に試す。
    Web UI（app.devrev.ai）の Network では tnt__user_ip + validate_required_fields: true の例がある。
    """
    out: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()

    def add(label: str, body: dict[str, Any]) -> None:
        sig = json.dumps(body, sort_keys=True, separators=(",", ":"))
        if sig in seen:
            return
        seen.add(sig)
        out.append((label, body))

    cid = conversation_id.strip()
    for fk in _custom_field_keys_for_ip(settings):
        fk_tag = fk.replace("__", "_")
        base: dict[str, Any] = {"id": cid, "custom_fields": {fk: user_ip}}
        add(f"configured__{fk_tag}", _conversation_update_body(settings, cid, user_ip, custom_field_key=fk))
        add(f"omit_custom_schema_spec__{fk_tag}", dict(base))
        add(f"schema_tenant_fragment_false__{fk_tag}", {
            **base,
            "custom_schema_spec": {
                "tenant_fragment": False,
                "validate_required_fields": False,
            },
        })
        add(f"schema_tenant_fragment_true__{fk_tag}", {
            **base,
            "custom_schema_spec": {
                "tenant_fragment": True,
                "validate_required_fields": False,
            },
        })
        # app.devrev.ai の internal/conversations.update と同型（validate_required: true）
        add(f"schema_tenant_fragment_true_validate_true__{fk_tag}", {
            **base,
            "custom_schema_spec": {
                "tenant_fragment": True,
                "validate_required_fields": True,
            },
        })
    display_id = _conversation_display_id_from_don(conversation_id)
    if display_id and display_id != cid:
        for label, body in list(out):
            alt = dict(body)
            alt["id"] = display_id
            add(f"{label}__id_{display_id}", alt)
    return out


def _fragment_app_variants(
    settings: Settings,
    conversation_id: str,
    user_ip: str,
    fragments: list[str],
) -> list[tuple[str, dict[str, Any]]]:
    """conversations.get の custom_schema_fragments を apps に載せて試す（テナント別の 400 回避）。"""
    base_id = conversation_id.strip()
    out: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()

    def add(label: str, body: dict[str, Any]) -> None:
        sig = json.dumps(body, sort_keys=True, separators=(",", ":"))
        if sig in seen:
            return
        seen.add(sig)
        out.append((label, body))

    for fk in _custom_field_keys_for_ip(settings):
        fk_tag = fk.replace("__", "_")
        for i, frag in enumerate(fragments):
            if not isinstance(frag, str) or not frag.strip():
                continue
            frag = frag.strip()
            add(
                f"schema_apps_frag{i}__{fk_tag}",
                {
                    "id": base_id,
                    "custom_fields": {fk: user_ip},
                    "custom_schema_spec": {
                        "tenant_fragment": True,
                        "validate_required_fields": True,
                        "apps": [frag],
                    },
                },
            )
            add(
                f"schema_apps_frag{i}_tenant_false__{fk_tag}",
                {
                    "id": base_id,
                    "custom_fields": {fk: user_ip},
                    "custom_schema_spec": {
                        "tenant_fragment": False,
                        "validate_required_fields": False,
                        "apps": [frag],
                    },
                },
            )
    return out


def update_conversation_user_ip(
    settings: Settings,
    conversation_id: str,
    user_ip: str,
) -> dict[str, Any]:
    """
    conversations.update に custom_fields（既定キー tnt__user_ip、必要なら user_ip も併試）を送る。
    conversation_id は CONV-xx または会話の don id 形式を想定。
    """
    bearer = _bearer_token(settings)
    if not bearer:
        raise RuntimeError("No DEVREV_PAT or DEVREV_APPLICATION_ACCESS_TOKEN configured")

    headers = {
        "Authorization": _authorization_header(bearer),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    last: Optional[httpx.Response] = None
    with httpx.Client(timeout=20.0) as client:
        for label, body in _conversation_update_body_variants(
            settings, conversation_id, user_ip
        ):
            r = client.post(CONVERSATIONS_UPDATE_URL, headers=headers, json=body)
            last = r
            if r.status_code in (200, 201):
                if not label.startswith("configured__"):
                    logger.info(
                        "conversations.update succeeded with fallback strategy=%s",
                        label,
                    )
                return r.json()
            if r.status_code == 400:
                logger.warning(
                    "conversations.update 400 strategy=%s response=%s",
                    label,
                    (r.text or "")[:500],
                )
                continue
            logger.warning(
                "conversations.update failed %s strategy=%s: %s",
                r.status_code,
                label,
                (r.text or "")[:800],
            )
            r.raise_for_status()

        if last is not None and last.status_code == 400:
            try:
                gr = client.get(
                    CONVERSATIONS_GET_URL,
                    headers=headers,
                    params={"id": conversation_id.strip()},
                )
            except httpx.HTTPError:
                logger.warning("conversations.get failed before fragment retry", exc_info=True)
                gr = None
            if gr is not None and gr.status_code == 200:
                conv = gr.json().get("conversation") or {}
                frags_raw = conv.get("custom_schema_fragments") or []
                frags = [f for f in frags_raw if isinstance(f, str)]
                if frags:
                    logger.info(
                        "conversations.update retry with custom_schema_fragments apps=%s",
                        frags,
                    )
                for label, body in _fragment_app_variants(
                    settings, conversation_id, user_ip, frags
                ):
                    r = client.post(CONVERSATIONS_UPDATE_URL, headers=headers, json=body)
                    last = r
                    if r.status_code in (200, 201):
                        logger.info(
                            "conversations.update succeeded with fragment strategy=%s",
                            label,
                        )
                        return r.json()
                    if r.status_code == 400:
                        logger.warning(
                            "conversations.update 400 strategy=%s response=%s",
                            label,
                            (r.text or "")[:500],
                        )
                        continue
                    logger.warning(
                        "conversations.update failed %s strategy=%s: %s",
                        r.status_code,
                        label,
                        (r.text or "")[:800],
                    )
                    r.raise_for_status()

    if last is not None:
        last.raise_for_status()
    raise RuntimeError("conversations.update: no response")

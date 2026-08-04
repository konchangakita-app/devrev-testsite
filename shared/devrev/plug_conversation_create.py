"""PLuG ウィジェットと同型の internal/conversations.create をサーバー経由で呼ぶ。"""

from __future__ import annotations

import logging
import secrets
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CONVERSATIONS_CREATE_URL = "https://api.devrev.ai/internal/conversations.create"


def create_plug_support_conversation(
    session_token: str,
    message: str,
    *,
    url_context: str,
) -> dict[str, Any]:
    """RevUser の PLuG session JWT で会話を作成し、初回メッセージを含める。"""
    body = message.strip()
    if not body:
        raise ValueError("message is required")

    token = session_token.strip()
    if not token:
        raise ValueError("session_token is required")

    headers = {
        "Authorization": token if token.lower().startswith("bearer ") else f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "X-Devrev-Client-Platform": "plug-widget",
    }
    payload = {
        "is_spam": False,
        "messages": [
            {
                "artifacts": [],
                "body": body,
                "client_ref": secrets.token_hex(16),
            }
        ],
        "metadata": {"url_context": url_context},
        "source_channel": "chat",
        "tag_names": [],
        "title": "",
        "type": "support",
    }

    with httpx.Client(timeout=20.0) as client:
        r = client.post(CONVERSATIONS_CREATE_URL, headers=headers, json=payload)

    if r.status_code not in (200, 201):
        logger.warning(
            "conversations.create failed %s: %s",
            r.status_code,
            (r.text or "")[:800],
        )
        r.raise_for_status()

    data = r.json()
    conv = data.get("conversation") or {}
    conv_id = conv.get("display_id") or conv.get("id")
    if not conv_id:
        raise RuntimeError("conversations.create: missing conversation id")
    return {
        "conversation_id": str(conv_id),
        "conversation_don": conv.get("id"),
        "devrev": data,
    }

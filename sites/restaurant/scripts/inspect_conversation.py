#!/usr/bin/env python3
"""
DevRev conversations.get で会話を1件取得し、custom_fields / custom_schema_fragments 等を表示する。
custom_fields の API 名が想定と一致しているかの切り分け用。

  cd sample-helpsite
  python3 scripts/inspect_conversation.py --id CONV-79
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

CONVERSATIONS_GET_URL = "https://api.devrev.ai/conversations.get"


def main() -> int:
    parser = argparse.ArgumentParser(description="conversations.get で会話を表示")
    parser.add_argument("--id", required=True, help="会話 id（CONV-79 または don:...）")
    args = parser.parse_args()

    import httpx

    from helpsite.plug_conversation_sync import _authorization_header, _bearer_token
    from helpsite.config import get_settings

    s = get_settings()
    bearer = _bearer_token(s)
    if not bearer:
        print("DEVREV_PAT または DEVREV_APPLICATION_ACCESS_TOKEN が必要です。", file=sys.stderr)
        return 2

    headers = {
        "Authorization": _authorization_header(bearer),
        "Accept": "application/json",
    }
    with httpx.Client(timeout=20.0) as client:
        r = client.get(
            CONVERSATIONS_GET_URL,
            headers=headers,
            params={"id": args.id.strip()},
        )
    if r.status_code != 200:
        print(f"HTTP {r.status_code}", file=sys.stderr)
        print((r.text or "")[:2000], file=sys.stderr)
        return 1

    data = r.json()
    conv = data.get("conversation") or {}
    summary = {
        "id": conv.get("id"),
        "display_id": conv.get("display_id"),
        "custom_fields": conv.get("custom_fields"),
        "custom_schema_fragments": conv.get("custom_schema_fragments"),
        "stock_schema_fragment": conv.get("stock_schema_fragment"),
        "subtype": conv.get("subtype"),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

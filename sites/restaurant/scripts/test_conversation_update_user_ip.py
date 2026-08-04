#!/usr/bin/env python3
"""
テスト用: DevRev conversations.update で会話の custom_fields（既定 user_ip）に値を書く。

  cd sample-helpsite
  python3 scripts/test_conversation_update_user_ip.py
  python3 scripts/test_conversation_update_user_ip.py --id CONV-79 --ip 203.0.113.1

使用トークン・フィールド名・custom_schema_spec は helpsite.config（.env）の
DEVREV_PAT / DEVREV_CONVERSATION_* と同じ。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="conversations.update で user_ip をテスト書き込み")
    parser.add_argument(
        "--id",
        default="CONV-79",
        help="会話 id（display_id 例: CONV-79 または don:...:conversation/79）",
    )
    parser.add_argument(
        "--ip",
        default="203.0.113.1",
        help="custom_fields に書く値（テスト用。既定は RFC5737 の文書用 IPv4）",
    )
    args = parser.parse_args()

    import httpx

    from helpsite.config import get_settings
    from helpsite.plug_conversation_sync import update_conversation_user_ip

    s = get_settings()
    if not (s.devrev_pat or "").strip() and not (s.devrev_application_access_token or "").strip():
        print("DEVREV_PAT または DEVREV_APPLICATION_ACCESS_TOKEN が必要です。", file=sys.stderr)
        return 2

    try:
        data = update_conversation_user_ip(s, args.id, args.ip)
    except httpx.HTTPStatusError as e:
        print(f"HTTP {e.response.status_code}: {e}", file=sys.stderr)
        if e.response is not None:
            print((e.response.text or "")[:1200], file=sys.stderr)
        return 1
    except Exception as e:
        print(f"失敗: {e}", file=sys.stderr)
        return 1

    print(json.dumps(data, indent=2, ensure_ascii=False)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
DEVREV_APPLICATION_ACCESS_TOKEN (AAT) が DevRev に受理されるかを auth-tokens.create で確認する。
レスポンスに含まれる access_token は標準出力に出さない（誤コピー防止）。
使い方: sample-helpsite ディレクトリで  python3 scripts/verify_devrev_aat.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# sample-helpsite をカレントにしたとき helpsite を import できるようにする
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import httpx

from helpsite.config import get_settings
from helpsite.devrev_service import _authorization_bearer

AUTH_TOKENS_URL = "https://api.devrev.ai/auth-tokens.create"


def main() -> int:
    s = get_settings()
    aat = (s.devrev_application_access_token or "").strip()
    if not aat:
        print("DEVREV_APPLICATION_ACCESS_TOKEN が空です。.env を確認してください。", file=sys.stderr)
        return 2

    rev_info: dict = {
        "user_ref": "aat-verify@localhost.test",
        "user_traits": {
            "email": "aat-verify@localhost.test",
            "display_name": "AAT verify",
            "phone_numbers": [],
        },
    }
    acc = (s.devrev_account_ref or "").strip()
    ws = (s.devrev_workspace_ref or "").strip()
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
        r = httpx.post(AUTH_TOKENS_URL, headers=headers, json=payload, timeout=30.0)
    except httpx.HTTPError as e:
        print(f"HTTP 接続エラー: {e}", file=sys.stderr)
        return 3

    print(f"HTTP {r.status_code}")

    if r.status_code in (200, 201):
        data = r.json()
        has_token = bool(data.get("access_token"))
        print("解釈: AAT は受理され、セッショントークン発行に成功した可能性が高いです。")
        print(f"      (access_token フィールドの有無: {has_token})")
        return 0

    if r.status_code == 401:
        print("解釈: AAT が無効・期限切れ・Authorization 形式不正の可能性が高いです。")
        _print_error_body(r)
        return 1

    if r.status_code == 403:
        print("解釈: 認証は通ったが、この操作が禁止されています（トークン種別・権限の確認）。")
        _print_error_body(r)
        return 1

    if r.status_code == 400:
        print(
            "解釈: AAT 自体は拒否されていない可能性がありますが、"
            "リクエスト本文（rev_info 等）が不正です。"
        )
        _print_error_body(r)
        return 1

    if r.status_code == 409:
        print(
            "解釈: AAT は受理された可能性がありますが、"
            "オブジェクトの競合（例: user_ref の重複）です。"
        )
        _print_error_body(r)
        return 1

    print("解釈: 上記以外のエラーです。本文を確認してください。")
    _print_error_body(r)
    return 1


def _print_error_body(r: httpx.Response) -> None:
    try:
        body = r.json()
        safe = {k: v for k, v in body.items() if k != "access_token"}
        print("応答（access_token はマスク）:", json.dumps(safe, ensure_ascii=False)[:800])
    except json.JSONDecodeError:
        print("応答テキスト先頭:", (r.text or "")[:500])


if __name__ == "__main__":
    sys.exit(main())

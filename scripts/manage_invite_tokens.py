#!/usr/bin/env python3
"""デモ招待トークンの発行・一覧・無効化（Agent / 運用者向け）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.database import SessionLocal  # noqa: E402
from shared.gate.models import Base  # noqa: E402
from shared.gate.tokens import (  # noqa: E402
    build_invite_url,
    create_invite_token,
    get_token_by_value,
    list_invite_tokens,
    revoke_invite_token,
)
from shared.database import engine  # noqa: E402
from shared.settings import resolved_demo_gate_base_url  # noqa: E402


def _ensure_tables() -> None:
    Base.metadata.create_all(bind=engine)


def cmd_create(args: argparse.Namespace) -> int:
    _ensure_tables()
    db = SessionLocal()
    try:
        row = create_invite_token(db, label=args.label)
        base = args.base_url or resolved_demo_gate_base_url()
        url = build_invite_url(base, row.token, path=args.path)
        print(f"id={row.id}")
        print(f"label={row.label or ''}")
        print(f"token={row.token}")
        print(f"invite_url={url}")
        return 0
    finally:
        db.close()


def cmd_list(args: argparse.Namespace) -> int:
    _ensure_tables()
    db = SessionLocal()
    try:
        rows = list_invite_tokens(db, include_revoked=args.all)
        base = args.base_url or resolved_demo_gate_base_url()
        if not rows:
            print("（トークンなし）")
            return 0
        for row in rows:
            status = "revoked" if row.revoked_at else "active"
            url = build_invite_url(base, row.token, path=args.path)
            print("---")
            print(f"id={row.id}")
            print(f"label={row.label or ''}")
            print(f"status={status}")
            print(f"created_at={row.created_at.isoformat()}")
            if row.last_used_at:
                print(f"last_used_at={row.last_used_at.isoformat()}")
            print(f"invite_url={url}")
        return 0
    finally:
        db.close()


def cmd_revoke(args: argparse.Namespace) -> int:
    _ensure_tables()
    db = SessionLocal()
    try:
        row = None
        if args.id is not None:
            from shared.gate.tokens import get_token_by_id

            row = get_token_by_id(db, args.id)
        elif args.token:
            row = get_token_by_value(db, args.token)
        if not row:
            print("トークンが見つかりません", file=sys.stderr)
            return 1
        revoke_invite_token(db, row)
        print(f"revoked id={row.id} label={row.label or ''}")
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="デモ招待トークン管理")
    parser.add_argument("--base-url", help="招待 URL のベース（未指定時は VERCEL_URL または localhost）")
    parser.add_argument("--path", default="/", help="招待 URL のパス（既定: /）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="新規トークン発行")
    p_create.add_argument("--label", default="", help="用途メモ")
    p_create.set_defaults(func=cmd_create)

    p_list = sub.add_parser("list", help="トークン一覧")
    p_list.add_argument("--all", action="store_true", help="無効化済みも含める")
    p_list.set_defaults(func=cmd_list)

    p_revoke = sub.add_parser("revoke", help="トークン無効化")
    p_revoke.add_argument("--id", type=int, help="トークン ID")
    p_revoke.add_argument("--token", help="トークン文字列")
    p_revoke.set_defaults(func=cmd_revoke)

    args = parser.parse_args()
    if args.command == "revoke" and args.id is None and not args.token:
        print("revoke には --id または --token が必要です", file=sys.stderr)
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

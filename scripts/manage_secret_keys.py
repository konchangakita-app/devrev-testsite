#!/usr/bin/env python3
"""Neon 上の SECRET_KEY（app_config）を確認する。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.config_store import CONFIG_KEY_SECRET_KEY, CONFIG_SCOPE_GLOBAL, ensure_config_tables  # noqa: E402
from shared.database import SessionLocal  # noqa: E402
from sqlalchemy import select  # noqa: E402
from shared.config.models import AppConfig  # noqa: E402


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return value[:4] + "…" + value[-4:]


def cmd_list(_: argparse.Namespace) -> int:
    ensure_config_tables()
    db = SessionLocal()
    try:
        row = db.scalars(
            select(AppConfig).where(
                AppConfig.scope == CONFIG_SCOPE_GLOBAL,
                AppConfig.key == CONFIG_KEY_SECRET_KEY,
            )
        ).first()
        if not row:
            print("（SECRET_KEY 未登録 — init_db.py を実行してください）")
            return 1
        print(f"scope={row.scope} key={row.key} value={_mask(row.value)} updated_at={row.updated_at}")
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Neon app_config の SECRET_KEY を確認")
    parser.add_argument("command", choices=["list"], help="list: 登録済みキーを表示（値はマスク）")
    args = parser.parse_args()
    if args.command == "list":
        return cmd_list(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Neon / SQLite 上のアプリ設定ストア（SECRET_KEY 等）。"""

from __future__ import annotations

import os
import secrets
from datetime import datetime
from functools import lru_cache

from sqlalchemy import select

from shared.config.models import AppConfig, ConfigBase
from shared.database import SessionLocal, engine

CONFIG_KEY_SECRET_KEY = "SECRET_KEY"
CONFIG_SCOPE_GLOBAL = "global"


def ensure_config_tables() -> None:
    ConfigBase.metadata.create_all(bind=engine)


def _bootstrap_secret() -> str:
    """初回のみ: 環境変数 SECRET_KEY があれば流用、なければランダム生成。"""
    env = (os.environ.get("SECRET_KEY") or "").strip()
    if env:
        return env
    return secrets.token_urlsafe(48)


def ensure_secret_key() -> str:
    """全サイト共通の SECRET_KEY を DB に確保して返す（init_db / 初回アクセス用）。"""
    ensure_config_tables()
    db = SessionLocal()
    try:
        row = db.scalars(
            select(AppConfig).where(
                AppConfig.scope == CONFIG_SCOPE_GLOBAL,
                AppConfig.key == CONFIG_KEY_SECRET_KEY,
            )
        ).first()
        if row:
            return row.value
        # 旧実装（scope 別）からの移行: 既存の SECRET_KEY を global に昇格
        legacy = db.scalars(
            select(AppConfig).where(AppConfig.key == CONFIG_KEY_SECRET_KEY)
        ).first()
        now = datetime.utcnow()
        value = legacy.value if legacy else _bootstrap_secret()
        db.add(
            AppConfig(
                scope=CONFIG_SCOPE_GLOBAL,
                key=CONFIG_KEY_SECRET_KEY,
                value=value,
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
        return value
    finally:
        db.close()


@lru_cache
def resolved_secret_key() -> str:
    """DB から全サイト共通 SECRET_KEY を取得。未設定なら Neon に自動作成。"""
    return ensure_secret_key()

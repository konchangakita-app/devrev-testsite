"""DevRev PLuG 環境変数の解決。

現行（2026-07）: 1 DevRev 組織につき PLuG app_id は 1 つのみ。
  → ルート `.env` の `DEVREV_PLUG_APP_ID` 等を全サイトで共有。

将来（マルチ PLuG チャット）: サイト別キーで上書き可能にする予約 API。
  → `DEVREV_PLUG_APP_ID__<site_slug>`（詳細は docs/future-multi-plug.md）
"""

from __future__ import annotations

import os

SITE_ENV_SEP = "__"


def site_env_key(base: str, site_slug: str) -> str:
    """例: DEVREV_PLUG_APP_ID + restaurant → DEVREV_PLUG_APP_ID__restaurant"""
    return f"{base}{SITE_ENV_SEP}{site_slug}"


def resolve_site_env(base: str, site_slug: str, shared_default: str = "") -> str:
    """サイト別 env → Settings の共通値 → プロセス環境の共通キー、の順で解決。"""
    specific = os.environ.get(site_env_key(base, site_slug), "").strip()
    if specific:
        return specific
    if (shared_default or "").strip():
        return shared_default.strip()
    return os.environ.get(base, "").strip()

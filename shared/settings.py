import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


def _default_sqlite_url() -> str:
    instance = REPO_ROOT / "sites" / "restaurant" / "instance" / "helpsite.db"
    return f"sqlite:///{instance}"


class SharedSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str = "dev-secret-change-me"
    database_url: str = ""


@lru_cache
def get_shared_settings() -> SharedSettings:
    return SharedSettings()


def _env_truthy(name: str) -> bool | None:
    """環境変数が未設定なら None、設定済みなら真偽値を返す。"""
    raw = os.environ.get(name)
    if raw is None:
        return None
    return raw.strip().lower() in ("1", "true", "yes", "on")


def is_demo_gate_enabled() -> bool:
    """デモゲート有効か。

    - DEMO_GATE_ENABLED が明示されていればそれに従う
    - 未設定時: Vercel（VERCEL=1）では自動 ON、ローカルでは OFF
    """
    explicit = _env_truthy("DEMO_GATE_ENABLED")
    if explicit is not None:
        return explicit
    return os.environ.get("VERCEL") == "1"


def resolved_demo_gate_base_url() -> str:
    """招待 URL 生成用ベース URL。

    - DEMO_GATE_BASE_URL があれば優先
    - Vercel では VERCEL_URL から自動生成（追加 env 不要）
    - それ以外はローカル既定
    """
    explicit = (os.environ.get("DEMO_GATE_BASE_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    vercel_url = (os.environ.get("VERCEL_URL") or "").strip()
    if vercel_url:
        return f"https://{vercel_url}".rstrip("/")
    return "http://localhost:5020"


def resolved_database_url() -> str:
    raw = (get_shared_settings().database_url or "").strip()
    if not raw:
        raw = _default_sqlite_url()
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://") and "+psycopg" not in raw.split("://", 1)[0]:
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw


def is_sqlite_database() -> bool:
    return resolved_database_url().startswith("sqlite")

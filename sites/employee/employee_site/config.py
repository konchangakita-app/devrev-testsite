from functools import lru_cache
from pathlib import Path
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.devrev.plug_env import resolve_site_env  # noqa: E402

SITE_SLUG = "employee"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"),),
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )

    secret_key: str = "dev-secret-change-me"
    url_prefix: str = "/employee"
    devrev_plug_app_id: str = ""
    devrev_plug_enable_session_recording: bool = False
    devrev_plug_prompt_user_ip: bool = False
    devrev_application_access_token: str = ""
    devrev_pat: str = ""
    devrev_account_ref: str = ""
    devrev_workspace_ref: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


def app_url(path: str = "/") -> str:
    prefix = get_settings().url_prefix.rstrip("/")
    if not path or path == "/":
        return f"{prefix}/"
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{prefix}{path}"


def resolved_plug_app_id() -> str:
    s = get_settings()
    return resolve_site_env("DEVREV_PLUG_APP_ID", SITE_SLUG, s.devrev_plug_app_id)


def resolved_application_access_token() -> str:
    s = get_settings()
    return resolve_site_env(
        "DEVREV_APPLICATION_ACCESS_TOKEN", SITE_SLUG, s.devrev_application_access_token
    )


def resolved_devrev_pat() -> str:
    s = get_settings()
    return resolve_site_env("DEVREV_PAT", SITE_SLUG, s.devrev_pat)

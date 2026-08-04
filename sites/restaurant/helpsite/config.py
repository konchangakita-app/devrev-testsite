from functools import lru_cache
from pathlib import Path
import sys

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent.parent
INSTANCE_DIR = BASE_DIR / "instance"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.devrev.plug_env import resolve_site_env  # noqa: E402

# マルチ PLuG 将来拡張用。resolve_site_env("DEVREV_PLUG_APP_ID", SITE_SLUG, ...) に渡す。
SITE_SLUG = "restaurant"


def _default_sqlite_url() -> str:
    return f"sqlite:///{INSTANCE_DIR / 'helpsite.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # リポジトリルート .env が正。サイト .env は移行期間の上書き用（非推奨）。
        env_file=(str(REPO_ROOT / ".env"), str(BASE_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )

    secret_key: str = "dev-secret-change-me"  # env: SECRET_KEY
    url_prefix: str = "/restaurant"  # env: URL_PREFIX — モノレポ root からのマウントパス
    # env: DATABASE_URL / DEVREV_* — リポジトリルート .env に一括設定
    database_url: str = ""
    devrev_plug_app_id: str = ""
    # PLuG の Web セッション記録（Session replay）。devrev.ai/docs/plug/session-recording 参照。DevRev 管理画面の Session Replays 設定と併用。
    devrev_plug_enable_session_recording: bool = False
    # true のとき、会話 ID 取得後に IP 入力パネルを出してから addSessionProperties / conversations.update（PAT 時）
    devrev_plug_prompt_user_ip: bool = True
    devrev_application_access_token: str = ""
    # conversations.update（会話 custom_fields の user_ip 等）用。env: DEVREV_PAT（ps_… 推奨）。未設定時は AAT を試す。
    devrev_pat: str = ""
    # conversations.update の custom_schema_spec を送るか。400 bad_request のとき false で custom_fields のみ送ると直るテナントがある。
    devrev_conversation_update_send_schema_spec: bool = True
    devrev_conversation_update_tenant_fragment: bool = True
    devrev_conversation_update_validate_required_fields: bool = False
    # 会話カスタムフィールド: 人間の呼び方は user_ip。API（conversations.update の custom_fields）では tnt__ 接頭辞が付くことが多い（例: tnt__user_ip）。別名のテナントは env で上書き。
    devrev_conversation_custom_field_user_ip: str = "tnt__user_ip"
    # auth-tokens.create の rev_info（任意）。空なら送らない。B2B でアカウント／WS を分けるときだけ設定。
    devrev_account_ref: str = ""
    devrev_workspace_ref: str = ""
    # auth-tokens.create の user_ref: member_id（mbr:{id}）| email（verified 調査用）
    devrev_plug_user_ref: str = "member_id"
    # auth-tokens.create の requested_token_type: session | session_rev_public
    devrev_plug_requested_token_type: str = "session"
    # true: 登録/ログイン時の auth-tokens.create を遅延（PLuG init まで RevUser を作らない）
    devrev_plug_defer_session_on_auth: bool = False
    # 任意。設定時は Authorization がこの値と一致すれば「管理者」として全ユーザ参照可（ps_ 形式を推奨）
    admin_api_key: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def coerce_database_url(cls, v: object) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return _default_sqlite_url()
        return str(v)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def normalize_database_url(url: str) -> str:
    """postgres:// や postgresql:// を SQLAlchemy + psycopg 向けに正規化。"""
    raw = (url or "").strip()
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://") and "+psycopg" not in raw.split("://", 1)[0]:
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw


def resolved_database_url() -> str:
    return normalize_database_url(get_settings().database_url)


def is_sqlite_database() -> bool:
    return resolved_database_url().startswith("sqlite")


def app_url(path: str = "/") -> str:
    """テンプレート・リダイレクト用の絶対パス（url_prefix 付き）。"""
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

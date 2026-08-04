import json
from typing import Any, Optional

from itsdangerous import BadSignature, URLSafeSerializer

from shared.config_store import resolved_secret_key

COOKIE_NAME = "demo_gate_session"
SERIALIZER_SALT = "demo-gate-v1"


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(resolved_secret_key(), salt=SERIALIZER_SALT)


def sign_gate_session(token_id: int) -> str:
    return _serializer().dumps({"tid": token_id})


def read_gate_session(cookie_value: Optional[str]) -> Optional[int]:
    if not cookie_value:
        return None
    try:
        data: dict[str, Any] = _serializer().loads(cookie_value)
    except BadSignature:
        return None
    tid = data.get("tid")
    if isinstance(tid, int):
        return tid
    if isinstance(tid, str) and tid.isdigit():
        return int(tid)
    return None

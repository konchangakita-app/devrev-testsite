import secrets
import string


def generate_api_key() -> str:
    """PetStore と同型: ps_live_ + 32 文字の英数字。"""
    alphabet = string.ascii_letters + string.digits
    key_body = "".join(secrets.choice(alphabet) for _ in range(32))
    return f"ps_live_{key_body}"

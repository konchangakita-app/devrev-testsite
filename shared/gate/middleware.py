from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from shared.database import SessionLocal
from shared.gate.cookie import COOKIE_NAME, read_gate_session, sign_gate_session
from shared.gate.tokens import (
    INVITE_QUERY_PARAM,
    get_token_by_id,
    get_token_by_value,
    is_token_usable,
    strip_invite_query,
    touch_token_used,
)
from shared.settings import is_demo_gate_enabled

EXEMPT_PATHS = {"/health"}
EXEMPT_PREFIXES = ("/validation/crawl",)

GATE_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>アクセス制限 — KON Group Demo</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 32rem; margin: 4rem auto; padding: 0 1rem; color: #1c1917; line-height: 1.6; }
    h1 { font-size: 1.35rem; margin-bottom: 0.75rem; }
    p { color: #57534e; margin: 0; }
  </style>
</head>
<body>
  <h1>デモサイトへのアクセスには招待が必要です</h1>
  <p>このサイトは限定公開のデモです。配布された招待リンクから初回アクセスしてください。</p>
</body>
</html>"""


class DemoGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not is_demo_gate_enabled():
            return await call_next(request)

        path = request.url.path
        if path in EXEMPT_PATHS or path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)

        invite_value = request.query_params.get(INVITE_QUERY_PARAM)
        if invite_value:
            return self._handle_invite_link(request, invite_value, call_next)

        token_id = read_gate_session(request.cookies.get(COOKIE_NAME))
        if token_id is not None and self._cookie_token_valid(token_id):
            return await call_next(request)

        return HTMLResponse(GATE_HTML, status_code=403)

    def _handle_invite_link(
        self, request: Request, invite_value: str, call_next
    ) -> Response:
        db = SessionLocal()
        try:
            row = get_token_by_value(db, invite_value.strip())
            if not is_token_usable(row):
                return HTMLResponse(GATE_HTML, status_code=403)
            touch_token_used(db, row)
            token_id = row.id
        finally:
            db.close()

        redirect_url = strip_invite_query(str(request.url))
        response: Response = RedirectResponse(redirect_url, status_code=302)
        response.set_cookie(
            key=COOKIE_NAME,
            value=sign_gate_session(token_id),
            httponly=True,
            samesite="lax",
            path="/",
            secure=request.url.scheme == "https",
            max_age=60 * 60 * 24 * 365,
        )
        return response

    def _cookie_token_valid(self, token_id: int) -> bool:
        db = SessionLocal()
        try:
            row = get_token_by_id(db, token_id)
            return is_token_usable(row)
        finally:
            db.close()

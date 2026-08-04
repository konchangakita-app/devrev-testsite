import logging
import re
import secrets
from enum import Enum
from datetime import date
from typing import Any, Optional, Union

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from werkzeug.security import check_password_hash, generate_password_hash

from helpsite.admin_user import router as admin_api_router
from helpsite.api_keys import generate_api_key
from helpsite.config import BASE_DIR, app_url, get_settings, resolved_application_access_token, resolved_devrev_pat, resolved_plug_app_id
from helpsite.database import get_db
from helpsite.devrev_service import (
    request_plug_session_token,
    request_plug_session_token_for_ref,
    session_token_valid_for_plug,
)
from helpsite.models import User
from helpsite.plug_conversation_sync import update_conversation_user_ip
from shared.devrev.plug_conversation_create import create_plug_support_conversation
from shared.config_store import resolved_secret_key
from helpsite.reservations_demo import (
    STATUS_LABELS,
    add_reservation,
    cancel_reservation_for_user,
    list_reservations,
    list_reservations_for_user,
    min_visit_date,
    update_status,
)

logger = logging.getLogger(__name__)

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

settings = get_settings()

_restaurant_path = settings.url_prefix.rstrip("/") or "/restaurant"

app = FastAPI(title="KON Restaurant Demo", docs_url=None, redoc_url=None)
app.include_router(admin_api_router, prefix="/api")
app.add_middleware(
    SessionMiddleware,
    secret_key=resolved_secret_key(),
    session_cookie="helpsite_session",
    max_age=86400 * 7,
    path=_restaurant_path,
    same_site="lax",
    https_only=False,
)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

from starlette.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["app_url"] = app_url


def ensure_csrf(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def validate_csrf(request: Request, token: Optional[str]) -> None:
    if not token or token != request.session.get("csrf_token"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def plug_template_context(request: Request) -> dict[str, Any]:
    s = get_settings()
    plug_app_id = resolved_plug_app_id()
    plug_session_token = request.session.get("devrev_session_token") or None
    if plug_session_token and plug_app_id and not session_token_valid_for_plug(
        plug_session_token, plug_app_id
    ):
        request.session.pop("devrev_session_token", None)
        plug_session_token = None
    can_sync_cf = bool(resolved_devrev_pat() or resolved_application_access_token())
    cf_api = (s.devrev_conversation_custom_field_user_ip or "tnt__user_ip").strip() or "tnt__user_ip"
    has_aat = bool(resolved_application_access_token())
    return {
        "plug_app_id": plug_app_id,
        "plug_session_token": plug_session_token,
        "plug_enabled": bool(plug_app_id),
        "plug_session_recording": s.devrev_plug_enable_session_recording,
        "plug_conversation_sync": can_sync_cf,
        "plug_prompt_user_ip": s.devrev_plug_prompt_user_ip,
        "plug_conversation_field_api_name": cf_api,
        "plug_auto_send": has_aat,
        "plug_user_ref_mode": s.devrev_plug_user_ref,
        "plug_requested_token_type": s.devrev_plug_requested_token_type,
    }


def resolve_plug_session_token(request: Request, user: Optional[User]) -> Optional[str]:
    """会員または匿名 PLuG 用 session token をサーバセッションから解決する。"""
    s = get_settings()
    plug_app_id = resolved_plug_app_id()
    if not resolved_application_access_token():
        return None

    if user is not None:
        token = request.session.get("devrev_session_token")
        if token and plug_app_id and session_token_valid_for_plug(token, plug_app_id):
            return token
        token = request_plug_session_token(user, s)
        if token:
            request.session["devrev_session_token"] = token
        return token

    anon_ref = request.session.get("plug_anon_user_ref")
    if not anon_ref:
        anon_ref = f"anon:{secrets.token_urlsafe(12)}"
        request.session["plug_anon_user_ref"] = anon_ref

    token = request.session.get("devrev_anon_session_token")
    if token and plug_app_id and session_token_valid_for_plug(token, plug_app_id):
        return token

    token = request_plug_session_token_for_ref(anon_ref, s, display_name="Guest")
    if token:
        request.session["devrev_anon_session_token"] = token
    return token


def optional_user(request: Request, db: Session) -> Optional[User]:
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.get(User, int(uid))


def optional_admin(request: Request, db: Session) -> Optional[User]:
    """管理者セッション（admin_user_id）のユーザーを返す。"""
    aid = request.session.get("admin_user_id")
    if not aid:
        return None
    user = db.get(User, int(aid))
    if not user or not user.is_admin:
        request.session.pop("admin_user_id", None)
        return None
    return user


def page_context(request: Request, db: Session) -> dict[str, Any]:
    ensure_csrf(request)
    member = optional_user(request, db)
    admin = optional_admin(request, db)
    plug_ctx = plug_template_context(request)
    if plug_ctx.get("plug_enabled"):
        if plug_ctx.get("plug_auto_send"):
            # 匿名でも create-conversation と PLuG init で同一 RevUser session を使う
            token = resolve_plug_session_token(request, member)
            if token:
                plug_ctx["plug_session_token"] = token
        elif member:
            plug_ctx["plug_session_token"] = (
                request.session.get("devrev_session_token") or plug_ctx.get("plug_session_token")
            )
    return {
        "user": member,
        "admin_user": admin,
        "csrf_token": request.session["csrf_token"],
        "url_prefix": _restaurant_path,
        **plug_ctx,
    }


def require_user(request: Request, db: Session) -> User:
    user = optional_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required",
        )
    return user


def require_admin(request: Request, db: Session) -> User:
    admin = optional_admin(request, db)
    if not admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin login required")
    return admin


def resolve_admin_page(request: Request, db: Session) -> Union[User, RedirectResponse]:
    """管理者 HTML ページ用。未ログイン→/admin/login。"""
    admin = optional_admin(request, db)
    if not admin:
        return RedirectResponse(app_url("/admin/login"), status_code=302)
    ensure_csrf(request)
    return admin


def admin_template_context(
    request: Request, db: Session, admin: User, admin_active: str
) -> dict[str, Any]:
    ensure_csrf(request)
    return {
        "user": optional_user(request, db),
        "admin_user": admin,
        "csrf_token": request.session["csrf_token"],
        "admin_active": admin_active,
        "url_prefix": _restaurant_path,
        **plug_template_context(request),
    }


def _assign_unique_api_key(db: Session, user: User) -> None:
    for _ in range(20):
        key = generate_api_key()
        if not db.scalars(select(User).where(User.api_key == key)).first():
            user.api_key = key
            return
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not allocate API key",
    )


class CsrfBody(BaseModel):
    csrf_token: str


class LoginBody(CsrfBody):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class RegisterBody(CsrfBody):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=6, max_length=128)
    email: str = Field(min_length=3, max_length=120)


class PlugConversationSyncBody(CsrfBody):
    """PLuG で会話 ID が分かったあと、サーバから conversations.update する用。"""

    conversation_id: str = Field(min_length=3, max_length=512)
    user_ip: Optional[str] = Field(default=None, max_length=64)


class PlugCreateConversationBody(CsrfBody):
    """4択プロンプト等から初回メッセージ付き会話をサーバ経由で作成する。"""

    message: str = Field(min_length=1, max_length=2000)


class ContactCategory(str, Enum):
    account = "account"
    service = "service"
    billing = "billing"
    bug = "bug"
    other = "other"


CONTACT_CATEGORY_LABELS: dict[ContactCategory, str] = {
    ContactCategory.account: "ログイン・会員登録について",
    ContactCategory.service: "サービスの使い方について",
    ContactCategory.billing: "料金・お支払いについて",
    ContactCategory.bug: "不具合・障害について",
    ContactCategory.other: "その他",
}


class ContactBody(CsrfBody):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=20)
    category: ContactCategory
    subject: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=2000)
    agree_privacy: bool


class ReserveBody(CsrfBody):
    visit_date: str = Field(min_length=10, max_length=10)
    time_slot: str = Field(min_length=4, max_length=8)
    meal_type: str = Field(pattern=r"^(lunch|dinner)$")
    party_size: int = Field(ge=2, le=8)
    seat_type: str = Field(pattern=r"^(table|private)$")
    course: str = Field(pattern=r"^(kon-standard|kon-season|chef-omakase)$")
    notes: Optional[str] = Field(default=None, max_length=500)


class AdminReservationStatusBody(CsrfBody):
    status: str = Field(pattern=r"^(confirmed|visited|cancelled)$")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _client_ip(request: Request) -> str:
    """プロキシ経由時は X-Forwarded-For の先頭（クライアント側）を優先する。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


_IPV4_RE = re.compile(r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d{1,3})\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d{1,3})$")


def _coerce_plug_submitted_ip(raw: Optional[str], fallback: str) -> str:
    """ブラウザからの user_ip。妥当そうな IPv4 / 簡易 IPv6 のみ通し、それ以外は fallback。"""
    if not raw:
        return fallback
    s = raw.strip()
    if len(s) > 64 or len(s) < 3:
        return fallback
    if _IPV4_RE.match(s):
        return s
    if ":" in s:
        allowed = set("0123456789abcdefABCDEF:.")
        if len(s) <= 45 and all(c in allowed for c in s):
            return s
    return fallback


@app.get("/api/client-ip")
def client_ip(request: Request) -> dict[str, Any]:
    """このリクエストを出したクライアントの IP（推定）。デバッグ・ngrok 検証用。"""
    xff = request.headers.get("x-forwarded-for")
    return {
        "ip": _client_ip(request),
        "x_forwarded_for": xff,
        "direct_peer": request.client.host if request.client else None,
    }


@app.get("/api/user-context")
def user_context_for_plug(request: Request) -> dict[str, str]:
    """PLuG の addSessionProperties 用。user_ip は会話 CF 用（Webhook 経由のほか、/api/plug/sync-conversation-custom-fields でもサーバ推定で書ける）。"""
    return {
        "city": "ApiTokyo",
        "region": "api-kanto",
        "demo_source": "sample-helpsite-api",
        "demo_region": "from_user_context",
        "user_ip": _client_ip(request),
    }


@app.post("/api/plug/sync-conversation-custom-fields")
def plug_sync_conversation_custom_fields(
    request: Request,
    body: PlugConversationSyncBody,
) -> JSONResponse:
    """
    DevRev conversations.update で会話の user_ip 系カスタムフィールドを書く。
    body.user_ip が無い・不正なときは _client_ip(request) を使う。
    """
    validate_csrf(request, body.csrf_token)
    s = get_settings()
    if not resolved_devrev_pat() and not resolved_application_access_token():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Set DEVREV_PAT or DEVREV_APPLICATION_ACCESS_TOKEN",
        )
    fallback = _client_ip(request)
    user_ip = _coerce_plug_submitted_ip(body.user_ip, fallback)
    try:
        data = update_conversation_user_ip(s, body.conversation_id, user_ip)
    except httpx.HTTPStatusError as e:
        detail = (e.response.text if e.response is not None else str(e))[:800]
        logger.warning("conversations.update HTTP error: %s", detail)
        upstream = e.response.status_code if e.response is not None else None
        status_out = (
            status.HTTP_400_BAD_REQUEST
            if upstream == 400
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=status_out, detail=detail) from e
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("conversations.update failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e
    return JSONResponse({"ok": True, "user_ip": user_ip, "devrev": data})


@app.get("/api/plug/session-token")
def plug_session_token(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    """PLuG fetchSessionToken 用。ウィジェットとサーバで同一 RevUser session を共有する。"""
    user = optional_user(request, db)
    token = resolve_plug_session_token(request, user)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Set DEVREV_APPLICATION_ACCESS_TOKEN for PLuG session",
        )
    return JSONResponse({"access_token": token})


@app.post("/api/plug/create-conversation")
def plug_create_conversation(
    request: Request,
    body: PlugCreateConversationBody,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """PLuG 初回メッセージを conversations.create で送信し、会話 ID を返す。"""
    validate_csrf(request, body.csrf_token)
    user = optional_user(request, db)
    token = resolve_plug_session_token(request, user)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Set DEVREV_APPLICATION_ACCESS_TOKEN for PLuG auto-send",
        )
    url_context = str(request.headers.get("referer") or request.url_for("index"))
    try:
        result = create_plug_support_conversation(
            token,
            body.message.strip(),
            url_context=url_context,
        )
    except httpx.HTTPStatusError as e:
        detail = (e.response.text if e.response is not None else str(e))[:800]
        logger.warning("conversations.create HTTP error: %s", detail)
        upstream = e.response.status_code if e.response is not None else None
        status_out = (
            status.HTTP_400_BAD_REQUEST
            if upstream == 400
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=status_out, detail=detail) from e
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception("conversations.create failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    return JSONResponse({"ok": True, **result})


@app.get("/contact", response_class=HTMLResponse)
def contact_page(request: Request, db: Session = Depends(get_db)) -> Any:
    return templates.TemplateResponse(request, "contact.html", page_context(request, db))


@app.post("/api/contact")
def submit_contact(request: Request, body: ContactBody) -> JSONResponse:
    """お問い合わせフォーム受付（デモ: ログ出力のみ、メール送信なし）。"""
    validate_csrf(request, body.csrf_token)
    if not body.agree_privacy:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="プライバシーポリシーへの同意が必要です",
        )
    category_label = CONTACT_CATEGORY_LABELS.get(body.category, body.category.value)
    logger.info(
        "contact inquiry: category=%s name=%r email=%r subject=%r message_len=%d ip=%s",
        category_label,
        body.name.strip(),
        body.email.strip(),
        body.subject.strip(),
        len(body.message),
        _client_ip(request),
    )
    return JSONResponse({"ok": True})


@app.get("/reserve", response_class=HTMLResponse)
def reserve_page(request: Request, db: Session = Depends(get_db)) -> Any:
    if not request.session.get("user_id"):
        return RedirectResponse(app_url("/"), status_code=302)
    user = optional_user(request, db)
    if not user:
        request.session.pop("user_id", None)
        return RedirectResponse(app_url("/"), status_code=302)
    ctx = page_context(request, db)
    ctx["min_visit_date"] = min_visit_date()
    return templates.TemplateResponse(request, "reserve.html", ctx)


@app.get("/member/reservations", response_class=HTMLResponse)
def member_reservations_page(request: Request, db: Session = Depends(get_db)) -> Any:
    if not request.session.get("user_id"):
        return RedirectResponse(app_url("/"), status_code=302)
    user = optional_user(request, db)
    if not user:
        request.session.pop("user_id", None)
        return RedirectResponse(app_url("/"), status_code=302)
    ctx = page_context(request, db)
    ctx["reservations"] = list_reservations_for_user(db, user.email)
    return templates.TemplateResponse(request, "member_reservations.html", ctx)


@app.post("/api/reserve")
def submit_reserve(
    request: Request,
    body: ReserveBody,
    db: Session = Depends(get_db),
) -> JSONResponse:
    validate_csrf(request, body.csrf_token)
    user = require_user(request, db)
    row = add_reservation(
        db,
        visit_date=body.visit_date.strip(),
        time_slot=body.time_slot.strip(),
        meal_type=body.meal_type,
        party_size=body.party_size,
        seat_type=body.seat_type,
        course=body.course,
        guest_name=user.username,
        guest_email=user.email,
        notes=(body.notes or "").strip(),
    )
    logger.info("demo reservation: %s user=%s", row["id"], user.username)
    return JSONResponse({"ok": True, "reservation": row})


@app.post("/api/my/reservations/{reservation_id}/cancel")
def cancel_my_reservation(
    reservation_id: str,
    request: Request,
    body: CsrfBody,
    db: Session = Depends(get_db),
) -> JSONResponse:
    validate_csrf(request, body.csrf_token)
    user = require_user(request, db)
    if not cancel_reservation_for_user(db, reservation_id, user.email):
        raise HTTPException(status_code=404, detail="Reservation not found or cannot cancel")
    return JSONResponse({"ok": True})


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request, db: Session = Depends(get_db)) -> Any:
    if optional_admin(request, db):
        return RedirectResponse(app_url("/admin"), status_code=302)
    ctx = page_context(request, db)
    return templates.TemplateResponse(request, "admin_login.html", ctx)


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)) -> Any:
    resolved = resolve_admin_page(request, db)
    if isinstance(resolved, RedirectResponse):
        return resolved
    admin = resolved
    reservations = list_reservations(db)
    today = date.today().isoformat()
    confirmed = sum(1 for r in reservations if r["status"] == "confirmed")
    user_count = len(db.scalars(select(User)).all())
    return templates.TemplateResponse(
        request,
        "admin_dashboard.html",
        {
            **admin_template_context(request, db, admin, "dashboard"),
            "user_count": user_count,
            "reservation_count": len(reservations),
            "confirmed_count": confirmed,
            "today_count": sum(
                1 for r in reservations if r["visit_date"] == today and r["status"] == "confirmed"
            ),
        },
    )


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request, db: Session = Depends(get_db)) -> Any:
    resolved = resolve_admin_page(request, db)
    if isinstance(resolved, RedirectResponse):
        return resolved
    admin = resolved
    users = db.scalars(select(User).order_by(User.id)).all()
    return templates.TemplateResponse(
        request,
        "admin_users.html",
        {
            **admin_template_context(request, db, admin, "users"),
            "users": users,
        },
    )


@app.get("/admin/reservations", response_class=HTMLResponse)
def admin_reservations_page(request: Request, db: Session = Depends(get_db)) -> Any:
    resolved = resolve_admin_page(request, db)
    if isinstance(resolved, RedirectResponse):
        return resolved
    admin = resolved
    return templates.TemplateResponse(
        request,
        "admin_reservations.html",
        {
            **admin_template_context(request, db, admin, "reservations"),
            "reservations": list_reservations(db),
        },
    )


@app.post("/api/admin/reservations/{reservation_id}/status")
def admin_update_reservation_status(
    reservation_id: str,
    request: Request,
    body: AdminReservationStatusBody,
    db: Session = Depends(get_db),
) -> JSONResponse:
    validate_csrf(request, body.csrf_token)
    require_admin(request, db)
    if body.status not in STATUS_LABELS:
        raise HTTPException(status_code=400, detail="Invalid status")
    if not update_status(db, reservation_id, body.status):
        raise HTTPException(status_code=404, detail="Reservation not found")
    return JSONResponse({"ok": True})


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)) -> Any:
    return templates.TemplateResponse(request, "index.html", page_context(request, db))


@app.get("/member", response_class=HTMLResponse)
def member_page(request: Request, db: Session = Depends(get_db)) -> Any:
    uid = request.session.get("user_id")
    if not uid:
        return RedirectResponse(app_url("/"), status_code=302)
    user = db.get(User, int(uid))
    if not user:
        request.session.pop("user_id", None)
        return RedirectResponse(app_url("/"), status_code=302)

    ensure_csrf(request)
    s = get_settings()
    if resolved_application_access_token() and not request.session.get("devrev_session_token"):
        token = request_plug_session_token(user, s)
        if token:
            request.session["devrev_session_token"] = token
            db.commit()
        else:
            db.rollback()

    return templates.TemplateResponse(
        request,
        "member.html",
        page_context(request, db),
    )


@app.post("/auth/admin/login")
def auth_admin_login(
    request: Request,
    body: LoginBody,
    db: Session = Depends(get_db),
) -> JSONResponse:
    validate_csrf(request, body.csrf_token)
    user = db.scalars(select(User).where(User.username == body.username.strip())).first()
    if not user or not check_password_hash(user.password_hash, body.password):
        raise HTTPException(status_code=401, detail="ユーザー名またはパスワードが正しくありません")
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="管理者アカウントではありません")
    request.session["admin_user_id"] = user.id
    return JSONResponse({"ok": True, "redirect": app_url("/admin")})


@app.post("/auth/admin/logout")
def auth_admin_logout(request: Request, body: CsrfBody) -> JSONResponse:
    validate_csrf(request, body.csrf_token)
    request.session.pop("admin_user_id", None)
    ensure_csrf(request)
    return JSONResponse({"ok": True, "redirect": app_url("/admin/login")})


def _try_devrev_session(request: Request, db: Session, user: User) -> None:
    request.session.pop("devrev_session_token", None)
    # 匿名 PLuG トークンは会員トークンと併存すると Cookie が 4KB 超過しブラウザが破棄する
    request.session.pop("devrev_anon_session_token", None)
    request.session.pop("plug_anon_user_ref", None)
    s = get_settings()
    if not resolved_application_access_token():
        db.commit()
        return
    if s.devrev_plug_defer_session_on_auth:
        db.commit()
        return
    token = request_plug_session_token(user, s)
    if token:
        request.session["devrev_session_token"] = token
    db.commit()


@app.post("/auth/login")
def auth_login(
    request: Request,
    body: LoginBody,
    db: Session = Depends(get_db),
) -> JSONResponse:
    validate_csrf(request, body.csrf_token)
    user = db.scalars(select(User).where(User.username == body.username.strip())).first()
    if not user or not check_password_hash(user.password_hash, body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    request.session["user_id"] = user.id
    _try_devrev_session(request, db, user)
    return JSONResponse({"ok": True, "redirect": app_url("/member")})


@app.post("/auth/register")
def auth_register(
    request: Request,
    body: RegisterBody,
    db: Session = Depends(get_db),
) -> JSONResponse:
    validate_csrf(request, body.csrf_token)
    email = str(body.email).strip()
    username = body.username.strip()
    if db.scalars(select(User).where(User.username == username)).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.scalars(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(body.password, method="pbkdf2:sha256"),
    )
    _assign_unique_api_key(db, user)
    db.add(user)
    db.flush()
    request.session["user_id"] = user.id
    _try_devrev_session(request, db, user)
    return JSONResponse({"ok": True, "redirect": app_url("/member")})


@app.post("/auth/logout")
def auth_logout(
    request: Request,
    body: CsrfBody,
    db: Session = Depends(get_db),
) -> JSONResponse:
    validate_csrf(request, body.csrf_token)
    request.session.pop("user_id", None)
    request.session.pop("devrev_session_token", None)
    ensure_csrf(request)
    return JSONResponse({"ok": True, "redirect": app_url("/")})

import secrets
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware
from starlette.templating import Jinja2Templates

from employee_site.articles import Article, get_article, load_articles, search_articles
from employee_site.config import BASE_DIR, app_url, get_settings, resolved_application_access_token, resolved_plug_app_id
from employee_site.devrev_service import (
    request_plug_session_token,
    request_plug_session_token_for_ref,
    session_token_valid_for_plug,
)
from employee_site.employees import Employee, find_employee_by_id, find_employee_by_username, verify_password
from shared.config_store import resolved_secret_key
from shared.devrev.plug_conversation_create import create_plug_support_conversation

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

settings = get_settings()
_employee_path = settings.url_prefix.rstrip("/") or "/employee"

app = FastAPI(title="KON Employee Help", docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=resolved_secret_key(),
    session_cookie="employee_session",
    max_age=86400 * 7,
    path=_employee_path,
    same_site="lax",
    https_only=False,
)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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


def optional_employee(request: Request) -> Optional[Employee]:
    employee_id = request.session.get("employee_id")
    if not employee_id:
        return None
    return find_employee_by_id(str(employee_id))


def plug_template_context(request: Request) -> dict[str, Any]:
    plug_app_id = resolved_plug_app_id()
    plug_session_token = request.session.get("devrev_session_token") or None
    if plug_session_token and plug_app_id and not session_token_valid_for_plug(
        plug_session_token, plug_app_id
    ):
        request.session.pop("devrev_session_token", None)
        plug_session_token = None
    return {
        "plug_app_id": plug_app_id,
        "plug_session_token": plug_session_token,
        "plug_enabled": bool(plug_app_id),
        "plug_session_recording": settings.devrev_plug_enable_session_recording,
        "plug_auto_send": bool(resolved_application_access_token()),
    }


def resolve_plug_session_token(request: Request, employee: Optional[Employee]) -> Optional[str]:
    plug_app_id = resolved_plug_app_id()
    if not resolved_application_access_token():
        return None

    if employee is not None:
        token = request.session.get("devrev_session_token")
        if token and plug_app_id and session_token_valid_for_plug(token, plug_app_id):
            return token
        token = request_plug_session_token(employee, settings)
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

    token = request_plug_session_token_for_ref(anon_ref, settings, display_name="Guest")
    if token:
        request.session["devrev_anon_session_token"] = token
    return token


def page_context(request: Request) -> dict[str, Any]:
    ensure_csrf(request)
    employee = optional_employee(request)
    plug_ctx = plug_template_context(request)
    if plug_ctx.get("plug_enabled") and plug_ctx.get("plug_auto_send"):
        token = resolve_plug_session_token(request, employee)
        if token:
            plug_ctx["plug_session_token"] = token
    return {
        "employee": employee,
        "csrf_token": request.session["csrf_token"],
        "url_prefix": _employee_path,
        **plug_ctx,
    }


class CsrfBody(BaseModel):
    csrf_token: str


class LoginBody(CsrfBody):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=4, max_length=128)


class PlugCreateConversationBody(CsrfBody):
    message: str = Field(min_length=1, max_length=2000)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "site": "employee"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            **page_context(request),
            "articles": load_articles(),
        },
    )


@app.get("/search", response_class=HTMLResponse)
def search_page(request: Request, q: str = "") -> HTMLResponse:
    query = q.strip()
    results = search_articles(query) if query else []
    return templates.TemplateResponse(
        request,
        "search.html",
        {
            **page_context(request),
            "query": query,
            "results": results,
        },
    )


@app.get("/articles/{slug}", response_class=HTMLResponse)
def article_page(request: Request, slug: str) -> HTMLResponse:
    article = get_article(slug)
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return templates.TemplateResponse(
        request,
        "article.html",
        {
            **page_context(request),
            "article": article,
        },
    )


@app.post("/api/login")
def api_login(request: Request, body: LoginBody) -> JSONResponse:
    validate_csrf(request, body.csrf_token)
    employee = find_employee_by_username(body.username)
    if not employee or not verify_password(employee, body.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    request.session["employee_id"] = employee.employee_id
    request.session.pop("devrev_session_token", None)

    token = request_plug_session_token(employee, settings)
    if token:
        request.session["devrev_session_token"] = token

    return JSONResponse(
        {
            "ok": True,
            "employee": {
                "employee_id": employee.employee_id,
                "display_name": employee.display_name,
                "department": employee.department,
            },
            "plug_session": bool(token),
        }
    )


@app.post("/api/logout")
def api_logout(request: Request, body: CsrfBody) -> JSONResponse:
    validate_csrf(request, body.csrf_token)
    request.session.pop("employee_id", None)
    request.session.pop("devrev_session_token", None)
    return JSONResponse({"ok": True})


@app.get("/api/user-context")
def user_context_for_plug(request: Request) -> dict[str, str]:
    employee = optional_employee(request)
    ctx = {
        "demo_source": "employee-helpsite",
        "site": "employee",
    }
    if employee:
        ctx.update(
            {
                "employee_id": employee.employee_id,
                "department": employee.department,
                "display_name": employee.display_name,
            }
        )
    return ctx


@app.get("/api/plug/session-token")
def plug_session_token(request: Request) -> JSONResponse:
    employee = optional_employee(request)
    token = resolve_plug_session_token(request, employee)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Set DEVREV_APPLICATION_ACCESS_TOKEN for PLuG session",
        )
    return JSONResponse({"access_token": token})


@app.post("/api/plug/create-conversation")
def plug_create_conversation(request: Request, body: PlugCreateConversationBody) -> JSONResponse:
    validate_csrf(request, body.csrf_token)
    employee = optional_employee(request)
    token = resolve_plug_session_token(request, employee)
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY if e.response is None else status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from e
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return JSONResponse({"ok": True, **result})

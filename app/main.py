"""KON Group デモサイト群 — ルート FastAPI アプリ。"""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from shared.gate.middleware import DemoGateMiddleware
from shared.validation.store import ensure_validation_tables
from validation.crawl.routes import router as validation_crawl_router

REPO_ROOT = Path(__file__).resolve().parent.parent
RESTAURANT_ROOT = REPO_ROOT / "sites" / "restaurant"
EMPLOYEE_ROOT = REPO_ROOT / "sites" / "employee"
PORTAL_DIR = REPO_ROOT / "portal"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(RESTAURANT_ROOT) not in sys.path:
    sys.path.insert(0, str(RESTAURANT_ROOT))
if str(EMPLOYEE_ROOT) not in sys.path:
    sys.path.insert(0, str(EMPLOYEE_ROOT))

from helpsite.main import app as restaurant_app  # noqa: E402
from employee_site.main import app as employee_app  # noqa: E402
from portal.routes import router as portal_router  # noqa: E402

app = FastAPI(title="KON Group Demo Sites", docs_url=None, redoc_url=None)
app.add_middleware(DemoGateMiddleware)


@app.on_event("startup")
def ensure_validation_tables_on_startup() -> None:
    ensure_validation_tables()


app.include_router(validation_crawl_router)
app.mount("/portal-static", StaticFiles(directory=PORTAL_DIR / "static"), name="portal-static")
app.include_router(portal_router)
app.mount("/restaurant", restaurant_app)
app.mount("/employee", employee_app)


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "sites": ["portal", "restaurant", "employee"]}

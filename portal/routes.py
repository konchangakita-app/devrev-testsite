from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

PORTAL_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(PORTAL_DIR / "templates"))

router = APIRouter()

DEMO_SITES = [
    {
        "id": "restaurant",
        "path": "/restaurant/",
        "title": "お客様向けレストラン",
        "description": "架空レストラン KON の会員予約・お問い合わせ。DevRev PLuG（顧客向け）のデモ。",
        "status": "live",
        "badge": "顧客向け",
    },
    {
        "id": "employee",
        "path": "/employee/",
        "title": "社内向けヘルプ",
        "description": "就業規則・経費精算など、KON グループ従業員向けナレッジ（グループ共通）。",
        "status": "live",
        "badge": "社内向け",
    },
    {
        "id": "it-sier",
        "path": None,
        "title": "IT SIer サービス",
        "description": "障害報告・契約問い合わせなど IT サービス顧客向けサイト。",
        "status": "planned",
        "badge": "顧客向け",
    },
    {
        "id": "retail",
        "path": None,
        "title": "小売 EC / 店舗",
        "description": "注文・返品・配送に関する顧客向けサポートサイト。",
        "status": "planned",
        "badge": "顧客向け",
    },
]


@router.get("/", response_class=HTMLResponse)
def portal_index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"sites": DEMO_SITES},
    )

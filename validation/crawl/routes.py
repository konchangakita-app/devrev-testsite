"""DevRev Web Crawler 検証用ページ（デモゲート除外 /validation/crawl/）。"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.validation.store import get_or_create_run, run_state_dict, update_run

router = APIRouter(prefix="/validation/crawl", tags=["validation-crawl"])

RUN_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$"


def _marker(run_id: str, page: str) -> str:
    return f"VALIDATION-CRAWL-{run_id}-{page.upper()}"


def _html(title: str, marker: str, extra: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body>
  <h1>{title}</h1>
  <p data-validation-marker="{marker}">{marker}</p>
  {extra}
</body>
</html>"""


def _seed_links(run_id: str, unlink_for_unlink: bool) -> str:
    links = [
        f'<li><a href="/validation/crawl/{run_id}/keep">keep</a></li>',
        f'<li><a href="/validation/crawl/{run_id}/for-404">for-404</a></li>',
    ]
    if not unlink_for_unlink:
        links.append(f'<li><a href="/validation/crawl/{run_id}/for-unlink">for-unlink</a></li>')
    links.append(f'<li><a href="/validation/crawl/{run_id}/for-redirect">for-redirect</a></li>')
    return "<ul>\n" + "\n".join(links) + "\n</ul>"


class CrawlControlBody(BaseModel):
    for_404_is_gone: Optional[bool] = Field(default=None, description="True で for-404 を HTTP 404 にする")
    unlink_for_unlink: Optional[bool] = Field(
        default=None, description="True で起点ページから for-unlink へのリンクを除去"
    )
    redirect_enabled: Optional[bool] = Field(default=None, description="True で for-redirect をリダイレクト")
    redirect_target: Optional[str] = Field(
        default=None,
        description="リダイレクト先（相対パスまたは絶対 URL）。未指定時は keep ページ",
    )


@router.get("/{run_id}/status")
def crawl_status(run_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    row = get_or_create_run(db, run_id)
    return run_state_dict(row)


@router.post("/{run_id}/control")
def crawl_control(run_id: str, body: CrawlControlBody, db: Session = Depends(get_db)) -> dict[str, object]:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    row = update_run(db, run_id, **updates)
    return run_state_dict(row)


@router.get("/{run_id}", response_class=HTMLResponse)
@router.get("/{run_id}/", response_class=HTMLResponse)
def crawl_seed(run_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    row = get_or_create_run(db, run_id)
    marker = _marker(run_id, "seed")
    extra = _seed_links(run_id, row.unlink_for_unlink)
    return HTMLResponse(_html(f"Crawl validation seed ({run_id})", marker, extra))


@router.get("/{run_id}/keep", response_class=HTMLResponse)
def crawl_keep(run_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    get_or_create_run(db, run_id)
    marker = _marker(run_id, "keep")
    return HTMLResponse(_html(f"Crawl validation keep ({run_id})", marker))


@router.get("/{run_id}/for-404", response_class=HTMLResponse)
def crawl_for_404(run_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    row = get_or_create_run(db, run_id)
    if row.for_404_is_gone:
        raise HTTPException(status_code=404, detail="Page intentionally removed for validation")
    marker = _marker(run_id, "for-404")
    return HTMLResponse(_html(f"Crawl validation for-404 ({run_id})", marker))


@router.get("/{run_id}/for-unlink", response_class=HTMLResponse)
def crawl_for_unlink(run_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    get_or_create_run(db, run_id)
    marker = _marker(run_id, "for-unlink")
    return HTMLResponse(_html(f"Crawl validation for-unlink ({run_id})", marker))


@router.get("/{run_id}/for-redirect")
def crawl_for_redirect(run_id: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    row = get_or_create_run(db, run_id)
    if row.redirect_enabled:
        target = (row.redirect_target or "").strip() or f"/validation/crawl/{run_id}/keep"
        if target.startswith("/"):
            target = str(request.base_url).rstrip("/") + target
        return RedirectResponse(url=target, status_code=302)
    marker = _marker(run_id, "for-redirect")
    return HTMLResponse(_html(f"Crawl validation for-redirect ({run_id})", marker))

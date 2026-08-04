"""Vercel Serverless エントリ（FastAPI + Mangum）。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESTAURANT = ROOT / "sites" / "restaurant"
EMPLOYEE = ROOT / "sites" / "employee"
for path in (ROOT, RESTAURANT, EMPLOYEE):
    entry = str(path)
    if entry not in sys.path:
        sys.path.insert(0, entry)

from mangum import Mangum  # noqa: E402

from app.main import app  # noqa: E402

handler = Mangum(app, lifespan="off")

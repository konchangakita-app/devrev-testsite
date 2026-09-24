from datetime import datetime

from sqlalchemy.orm import Session

from shared.validation.models import CrawlValidationRun


def get_or_create_run(db: Session, run_id: str) -> CrawlValidationRun:
    row = db.get(CrawlValidationRun, run_id)
    if row is None:
        row = CrawlValidationRun(run_id=run_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def update_run(db: Session, run_id: str, **fields: object) -> CrawlValidationRun:
    row = get_or_create_run(db, run_id)
    for key, value in fields.items():
        setattr(row, key, value)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def run_state_dict(row: CrawlValidationRun) -> dict[str, object]:
    return {
        "run_id": row.run_id,
        "for_404_is_gone": row.for_404_is_gone,
        "unlink_for_unlink": row.unlink_for_unlink,
        "redirect_enabled": row.redirect_enabled,
        "redirect_target": row.redirect_target,
        "updated_at": row.updated_at.isoformat() + "Z",
    }

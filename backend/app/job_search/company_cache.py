from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.job_search.discovery import normalize_company_name
from app.models.company_ats_mapping import CompanyAtsMapping
from app.utils.time import utcnow


def get_cached_mapping(db: Session, company_name: str) -> CompanyAtsMapping | None:
    normalized = normalize_company_name(company_name)
    return db.scalar(
        select(CompanyAtsMapping).where(CompanyAtsMapping.company_name == normalized)
    )


def save_mapping(
    db: Session, company_name: str, source: str | None, slug: str | None
) -> None:
    normalized = normalize_company_name(company_name)
    db.add(
        CompanyAtsMapping(
            company_name=normalized, source=source, slug=slug, checked_at=utcnow()
        )
    )
    try:
        db.commit()
    except IntegrityError:
        # Another request already wrote this company_name (unique constraint) —
        # its result stands, this attempt is simply dropped.
        db.rollback()

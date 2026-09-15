from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db


router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/version")
def version_info(db: Session = Depends(get_db)):
    try:
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database revision unavailable") from exc
    if revision is None:
        raise HTTPException(status_code=503, detail="Database revision unavailable")
    return {
        "app_version": settings.app_version,
        "git_commit": settings.git_commit or None,
        "environment": settings.app_env,
        "database_revision": revision,
    }

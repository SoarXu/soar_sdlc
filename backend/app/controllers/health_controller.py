from fastapi import APIRouter

from app.core.config import settings


router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/version")
def version_info():
    return {
        "app_version": settings.app_version,
        "environment": settings.app_env,
    }

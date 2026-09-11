from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_system_admin
from app.db.session import get_db
from app.services import ldap_config_service, ldap_sync_service
from app.jobs.ldap_jobs import LdapSyncAlreadyRunning, run_ldap_sync_job, run_selected_ldap_sync
from app.views.ldap_view import (
    LdapConfigRead, LdapConfigWrite, LdapDirectoryPage, LdapSyncRequest,
    LdapSyncResponse, LdapSyncRunPage, LdapTestResult,
)


router = APIRouter()


@router.get("", response_model=LdapConfigRead)
def read_config(db: Session = Depends(get_db), _admin=Depends(require_system_admin)):
    return ldap_config_service.get_config(db)


@router.put("", response_model=LdapConfigRead)
def write_config(payload: LdapConfigWrite, db: Session = Depends(get_db), _admin=Depends(require_system_admin)):
    return ldap_config_service.save_config(db, payload)


@router.post("/test", response_model=LdapTestResult)
def test_config(db: Session = Depends(get_db), _admin=Depends(require_system_admin)):
    return ldap_config_service.test_config(db)


@router.get("/directory-users", response_model=LdapDirectoryPage)
def directory_users(
    q: str | None = Query(default=None, max_length=100),
    cursor: str | None = Query(default=None, max_length=2048),
    page_size: int = Query(default=50, ge=1, le=200),
    user_base_dn: str | None = Query(default=None, max_length=512),
    exclude_disabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return ldap_config_service.directory_users(
        db,
        q,
        cursor,
        page_size,
        user_base_dn=user_base_dn,
        exclude_disabled=exclude_disabled,
    )


@router.post("/sync", response_model=LdapSyncResponse)
def sync_users(
    payload: LdapSyncRequest,
    db: Session = Depends(get_db),
    admin=Depends(require_system_admin),
):
    try:
        return run_selected_ldap_sync(db, payload.items, admin.id)
    except LdapSyncAlreadyRunning as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "LDAP_SYNC_ALREADY_RUNNING", "message": "LDAP 同步任务正在运行"},
        ) from error


@router.post("/sync-bound-users", response_model=LdapSyncResponse)
def sync_bound_users(admin=Depends(require_system_admin)):
    try:
        return run_ldap_sync_job(admin.id)
    except LdapSyncAlreadyRunning as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "LDAP_SYNC_ALREADY_RUNNING", "message": "LDAP 同步任务正在运行"},
        ) from error


@router.get("/sync-runs", response_model=LdapSyncRunPage)
def sync_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return ldap_sync_service.list_sync_runs(db, page, page_size)

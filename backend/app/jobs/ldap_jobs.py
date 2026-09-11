from threading import Lock

from app.db.session import SessionLocal
from app.services.ldap_sync_service import sync_bound_users, sync_selected_users


class LdapSyncAlreadyRunning(Exception):
    pass


# This lock prevents overlap only within one application process. Multi-process
# deployments need a database or distributed lock before enabling this job.
_job_lock = Lock()


def run_ldap_sync_job(initiated_by_user_id: int | None = None) -> dict:
    if not _job_lock.acquire(blocking=False):
        raise LdapSyncAlreadyRunning()
    try:
        db = SessionLocal()
        try:
            return sync_bound_users(db, initiated_by_user_id)
        finally:
            db.close()
    finally:
        _job_lock.release()


def run_selected_ldap_sync(db, selections, initiated_by_user_id: int) -> dict:
    if not _job_lock.acquire(blocking=False):
        raise LdapSyncAlreadyRunning()
    try:
        return sync_selected_users(db, selections, initiated_by_user_id)
    finally:
        _job_lock.release()


def run_weekly_ldap_sync() -> dict | None:
    try:
        return run_ldap_sync_job(None)
    except LdapSyncAlreadyRunning:
        return None

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal, engine
from app.models.ldap_sync import LdapSyncItem, LdapSyncRun
from app.models.user import User


def _ldap_user(**overrides):
    suffix = uuid4().hex[:8]
    values = {
        "username": f"weekly_ldap_{suffix}",
        "full_name": "Before weekly sync",
        "password_hash": get_password_hash("unused-password"),
        "auth_source": "ldap",
        "ldap_external_id": str(uuid4()),
        "ldap_dn": f"CN={suffix},DC=example,DC=com",
        "is_active": True,
        "must_change_password": False,
        "deleted": 0,
    }
    values.update(overrides)
    return User(**values)


def _entry(user, **overrides):
    values = {
        "username": user.username,
        "employee_no": user.employee_no,
        "full_name": "After weekly sync",
        "email": user.email,
        "mobile": user.mobile,
        "department": "Directory",
        "external_id": user.ldap_external_id,
        "dn": user.ldap_dn,
        "enabled": True,
    }
    values.update(overrides)
    return values


def test_bound_sync_updates_only_existing_ldap_identities_and_continues_after_failure(monkeypatch):
    from app.services import ldap_config_service, ldap_sync_service
    from app.services.ldap_client import LdapNetworkError

    db = SessionLocal()
    first = _ldap_user()
    failing = _ldap_user()
    unlinked = User(
        username=f"not_linked_{uuid4().hex[:8]}", full_name="Unlinked",
        password_hash=get_password_hash("local-password"), auth_source="local",
        is_active=True, must_change_password=False, deleted=0,
    )
    db.add_all([first, failing, unlinked])
    db.commit()
    ids = first.id, failing.id, unlinked.id
    queried = []

    monkeypatch.setattr(ldap_config_service, "require_ready_config", lambda _db: SimpleNamespace())
    monkeypatch.setattr(ldap_config_service, "_password", lambda _config: "service-secret")

    def lookup(_config, password, external_id):
        assert password == "service-secret"
        queried.append(external_id)
        if external_id == failing.ldap_external_id:
            raise LdapNetworkError("LDAP 服务器不可达")
        return _entry(first)

    monkeypatch.setattr(ldap_sync_service.ldap_client, "search_user_by_external_id", lookup)
    try:
        result = ldap_sync_service.sync_bound_users(db, initiated_by_user_id=None)

        assert result["summary"]["updated"] == 1
        assert result["summary"]["failed"] == 1
        assert set(queried) == {first.ldap_external_id, failing.ldap_external_id}
        assert db.get(User, ids[0]).full_name == "After weekly sync"
        assert db.get(User, ids[1]).is_active is True
        assert db.get(User, ids[2]).full_name == "Unlinked"
        run = db.get(LdapSyncRun, result["run_id"])
        assert run.status == "partial_failed"
        assert db.query(LdapSyncItem).filter(LdapSyncItem.run_id == run.id).count() == 2
    finally:
        for user_id in ids:
            user = db.get(User, user_id)
            if user:
                db.delete(user)
        db.commit()
        db.close()


def test_config_failure_is_audited_without_disabling_bound_user(monkeypatch):
    from fastapi import HTTPException
    from app.services import ldap_config_service, ldap_sync_service

    db = SessionLocal()
    user = _ldap_user()
    db.add(user)
    db.commit()
    user_id = user.id
    monkeypatch.setattr(
        ldap_config_service,
        "require_ready_config",
        lambda _db: (_ for _ in ()).throw(HTTPException(status_code=409, detail="LDAP 集成尚未启用")),
    )
    try:
        result = ldap_sync_service.sync_bound_users(db, initiated_by_user_id=None)

        assert result["summary"]["failed"] == 1
        assert db.get(User, user_id).is_active is True
        run = db.get(LdapSyncRun, result["run_id"])
        assert run.status == "failed"
        item = db.query(LdapSyncItem).filter(LdapSyncItem.run_id == run.id).one()
        assert item.message == "LDAP 集成尚未启用"
    finally:
        db.delete(db.get(User, user_id))
        db.commit()
        db.close()


def test_successful_missing_directory_lookup_disables_bound_user(monkeypatch):
    from app.services import ldap_config_service, ldap_sync_service

    db = SessionLocal()
    user = _ldap_user()
    db.add(user)
    db.commit()
    user_id = user.id
    monkeypatch.setattr(ldap_config_service, "require_ready_config", lambda _db: SimpleNamespace())
    monkeypatch.setattr(ldap_config_service, "_password", lambda _config: "service-secret")
    monkeypatch.setattr(ldap_sync_service.ldap_client, "search_user_by_external_id", lambda *_args: None)
    try:
        result = ldap_sync_service.sync_bound_users(db, initiated_by_user_id=None)

        assert result["summary"]["updated"] == 1
        assert db.get(User, user_id).is_active is False
    finally:
        db.delete(db.get(User, user_id))
        db.commit()
        db.close()


def test_job_uses_its_own_session_and_process_lock(monkeypatch):
    from app.jobs import ldap_jobs

    calls = []

    class Session:
        def close(self):
            calls.append("close")

    session = Session()
    monkeypatch.setattr(ldap_jobs, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        ldap_jobs, "sync_bound_users",
        lambda db, initiated_by_user_id: calls.append((db, initiated_by_user_id)) or {"run_id": 1},
    )

    assert ldap_jobs.run_ldap_sync_job(42) == {"run_id": 1}
    assert calls == [(session, 42), "close"]
    assert ldap_jobs._job_lock.acquire(blocking=False)
    try:
        with pytest.raises(ldap_jobs.LdapSyncAlreadyRunning):
            ldap_jobs.run_ldap_sync_job(None)
    finally:
        ldap_jobs._job_lock.release()


def test_weekly_job_skips_process_local_overlap_without_stopping_scheduler():
    from app.jobs import ldap_jobs

    assert ldap_jobs._job_lock.acquire(blocking=False)
    try:
        assert ldap_jobs.run_weekly_ldap_sync() is None
    finally:
        ldap_jobs._job_lock.release()


def test_selected_sync_shares_the_process_lock(monkeypatch):
    from app.jobs import ldap_jobs

    monkeypatch.setattr(ldap_jobs, "sync_selected_users", lambda *_args: {"run_id": 1})
    assert ldap_jobs._job_lock.acquire(blocking=False)
    try:
        with pytest.raises(ldap_jobs.LdapSyncAlreadyRunning):
            ldap_jobs.run_selected_ldap_sync(object(), [], 42)
    finally:
        ldap_jobs._job_lock.release()


def test_admin_can_trigger_and_page_safe_sync_history(client, monkeypatch):
    from app.controllers import ldap_controller

    actor_ids = []
    monkeypatch.setattr(
        ldap_controller,
        "run_ldap_sync_job",
        lambda actor_id: actor_ids.append(actor_id) or {
            "run_id": 987, "summary": {"total": 0, "created": 0, "bound": 0, "updated": 0, "skipped": 0, "failed": 0}, "items": [],
        },
    )

    triggered = client.post("/api/v1/admin/ldap/sync-bound-users")
    history = client.get("/api/v1/admin/ldap/sync-runs?page=1&page_size=20")

    assert triggered.status_code == 200, triggered.text
    assert actor_ids and actor_ids[0] > 0
    assert history.status_code == 200, history.text
    body = history.json()
    assert body["page"] == 1 and body["page_size"] == 20
    assert "items" in body and "total" in body
    assert "password" not in history.text.casefold()


def test_sync_history_loads_first_failure_summaries_without_n_plus_one_queries():
    from app.services.ldap_sync_service import list_sync_runs

    db = SessionLocal()
    runs = [LdapSyncRun(status="failed", total_count=1, failed_count=1) for _ in range(3)]
    db.add_all(runs)
    db.flush()
    for index, run in enumerate(runs):
        db.add_all([
            LdapSyncItem(run_id=run.id, external_id=f"external-{index}", decision="update", status="failed", message=f"first-{index}"),
            LdapSyncItem(run_id=run.id, external_id=f"external-{index}", decision="update", status="failed", message=f"second-{index}"),
        ])
    db.commit()
    run_ids = [run.id for run in runs]
    statements = []

    def record_query(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_query)
    try:
        result = list_sync_runs(db, page=1, page_size=100)
    finally:
        event.remove(engine, "before_cursor_execute", record_query)
        db.query(LdapSyncItem).filter(LdapSyncItem.run_id.in_(run_ids)).delete(synchronize_session=False)
        db.query(LdapSyncRun).filter(LdapSyncRun.id.in_(run_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()

    summaries = {item["id"]: item["error_summary"] for item in result["items"] if item["id"] in run_ids}
    assert summaries == {run_id: f"first-{index}" for index, run_id in enumerate(run_ids)}
    assert len(statements) == 3
    failure_query = " ".join(statements[2].casefold().split())
    assert "min(ldap_sync_items.id)" in failure_query
    assert "group by ldap_sync_items.run_id" in failure_query
    assert " join " in failure_query


@pytest.mark.parametrize(
    ("path", "runner_name"),
    [
        ("/api/v1/admin/ldap/sync", "run_selected_ldap_sync"),
        ("/api/v1/admin/ldap/sync-bound-users", "run_ldap_sync_job"),
    ],
)
def test_manual_sync_overlap_returns_stable_structured_conflict(client, monkeypatch, path, runner_name):
    from app.controllers import ldap_controller
    from app.jobs.ldap_jobs import LdapSyncAlreadyRunning

    monkeypatch.setattr(
        ldap_controller,
        runner_name,
        lambda *_args, **_kwargs: (_ for _ in ()).throw(LdapSyncAlreadyRunning()),
    )
    response = client.post(path, json={"items": []} if path.endswith("/sync") else None)

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "LDAP_SYNC_ALREADY_RUNNING",
        "message": "LDAP 同步任务正在运行",
    }


@pytest.mark.parametrize("path", ["/api/v1/admin/ldap/sync-bound-users", "/api/v1/admin/ldap/sync-runs"])
def test_non_admin_cannot_trigger_or_read_sync_history(client, path):
    response = client.request(
        "POST" if path.endswith("sync-bound-users") else "GET",
        path,
        headers={"Authorization": f"Bearer {create_access_token('bob')}"},
    )
    assert response.status_code == 403

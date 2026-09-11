from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.user import User
from app.models.ldap_sync import LdapSyncItem, LdapSyncRun
from test_ldap_config_api import _payload


def _directory_user(external_id: str, **overrides):
    suffix = external_id[-8:].replace("-", "")
    item = {
        "username": f"ad_sync_{suffix}",
        "employee_no": f"E-{suffix}",
        "full_name": "AD Sync User",
        "email": f"ad_sync_{suffix}@example.com",
        "mobile": "13800000000",
        "department": "R&D",
        "external_id": external_id,
        "dn": f"CN=AD Sync {suffix},DC=example,DC=com",
        "enabled": True,
    }
    item.update(overrides)
    return item


def _configure(client):
    settings.__dict__["integration_encryption_key"] = Fernet.generate_key().decode()
    response = client.put("/api/v1/admin/ldap", json=_payload())
    assert response.status_code == 200, response.text
    from app.models.ldap_integration import LdapIntegrationConfig
    from app.services.ldap_config_service import _fingerprint

    db = SessionLocal()
    config = db.get(LdapIntegrationConfig, 1)
    config.tested_fingerprint = _fingerprint(config)
    config.enabled = True
    db.commit()
    db.close()


def test_sync_refetches_selected_user_and_creates_ldap_identity(client, monkeypatch):
    _configure(client)
    external_id = str(uuid4())
    entry = _directory_user(external_id)
    calls = []

    def refetch(_config, _password, requested_external_id):
        calls.append(requested_external_id)
        return entry

    monkeypatch.setattr("app.services.ldap_sync_service.ldap_client.search_user_by_external_id", refetch)
    response = client.post(
        "/api/v1/admin/ldap/sync",
        json={"items": [{"external_id": external_id, "decision": "create"}]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert calls == [external_id]
    assert body["summary"] == {"total": 1, "created": 1, "bound": 0, "updated": 0, "skipped": 0, "failed": 0}
    assert body["items"][0]["status"] == "created"
    assert isinstance(body["items"][0]["user_id"], int)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.ldap_external_id == external_id).one()
        assert user.username == entry["username"]
        assert user.employee_no == entry["employee_no"]
        assert user.auth_source == "ldap"
        assert user.must_change_password is False
        assert user.ldap_last_synced_at is not None
    finally:
        db.close()


def test_sync_can_bind_existing_user_without_replacing_its_id_or_admin_flag(client, monkeypatch):
    _configure(client)
    external_id = str(uuid4())
    employee_no = f"E-{uuid4().hex[:8]}"
    db = SessionLocal()
    existing = User(
        username=f"local_bind_{uuid4().hex[:8]}", full_name="Local User",
        employee_no=employee_no, password_hash=get_password_hash("test-only-password"),
        is_active=True, is_system_admin=False, must_change_password=False, deleted=0,
    )
    db.add(existing)
    db.commit()
    existing_id = existing.id
    db.close()
    entry = _directory_user(external_id, employee_no=employee_no)
    monkeypatch.setattr(
        "app.services.ldap_sync_service.ldap_client.search_user_by_external_id",
        lambda *_args: entry,
    )

    response = client.post(
        "/api/v1/admin/ldap/sync",
        json={"items": [{"external_id": external_id, "decision": "bind", "user_id": existing_id}]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["status"] == "bound"
    db = SessionLocal()
    try:
        bound = db.get(User, existing_id)
        assert bound is not None
        assert bound.ldap_external_id == external_id
        assert bound.auth_source == "ldap"
        assert bound.username == entry["username"]
        assert bound.is_system_admin is False
    finally:
        db.close()


def test_sync_uses_savepoints_so_one_failure_does_not_abort_other_items(client, monkeypatch):
    _configure(client)
    missing_id = str(uuid4())
    valid_id = str(uuid4())
    valid_entry = _directory_user(valid_id)

    def refetch(_config, _password, external_id):
        return None if external_id == missing_id else valid_entry

    monkeypatch.setattr("app.services.ldap_sync_service.ldap_client.search_user_by_external_id", refetch)
    response = client.post(
        "/api/v1/admin/ldap/sync",
        json={"items": [
            {"external_id": missing_id, "decision": "create"},
            {"external_id": valid_id, "decision": "create"},
        ]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"] == {"total": 2, "created": 1, "bound": 0, "updated": 0, "skipped": 0, "failed": 1}
    assert [item["status"] for item in body["items"]] == ["failed", "created"]


def test_linked_disabled_user_is_only_disabled_after_confirmed_ldap_result(client, monkeypatch):
    _configure(client)
    external_id = str(uuid4())
    db = SessionLocal()
    linked = User(
        username=f"linked_{uuid4().hex[:8]}", full_name="Linked User",
        password_hash=get_password_hash("test-only-password"), auth_source="ldap",
        ldap_external_id=external_id, is_active=True, must_change_password=False, deleted=0,
    )
    db.add(linked)
    db.commit()
    linked_id = linked.id
    db.close()
    monkeypatch.setattr(
        "app.services.ldap_sync_service.ldap_client.search_user_by_external_id",
        lambda *_args: _directory_user(external_id, enabled=False, employee_no=None),
    )
    response = client.post(
        "/api/v1/admin/ldap/sync",
        json={"items": [{"external_id": external_id, "decision": "update"}]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["status"] == "updated"
    db = SessionLocal()
    try:
        assert db.get(User, linked_id).is_active is False
    finally:
        db.close()


@pytest.mark.parametrize("auth", ["bob", None])
def test_non_admin_and_anonymous_cannot_sync_ldap_users(client, auth):
    headers = {"X-Test-No-Auth": "1"} if auth is None else {"Authorization": f"Bearer {create_access_token(auth)}"}
    response = client.post("/api/v1/admin/ldap/sync", json={"items": []}, headers=headers)
    assert response.status_code == (401 if auth is None else 403)


def test_bind_rejects_conflicting_employee_and_email_matches(client, monkeypatch):
    _configure(client)
    external_id = str(uuid4())
    db = SessionLocal()
    employee_user = User(
        username=f"employee_{uuid4().hex[:8]}", full_name="Employee Match",
        employee_no=f"E-{uuid4().hex[:8]}", email=f"employee_{uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("test-only-password"), is_active=True,
        must_change_password=False, deleted=0,
    )
    email_user = User(
        username=f"email_{uuid4().hex[:8]}", full_name="Email Match",
        email=f"email_{uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("test-only-password"), is_active=True,
        must_change_password=False, deleted=0,
    )
    db.add_all([employee_user, email_user])
    db.commit()
    employee_user_id = employee_user.id
    employee_no = employee_user.employee_no
    email = email_user.email
    db.close()
    entry = _directory_user(external_id, employee_no=employee_no, email=email)
    monkeypatch.setattr(
        "app.services.ldap_sync_service.ldap_client.search_user_by_external_id",
        lambda *_args: entry,
    )

    response = client.post(
        "/api/v1/admin/ldap/sync",
        json={"items": [{"external_id": external_id, "decision": "bind", "user_id": employee_user_id}]},
    )

    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["status"] == "failed"
    assert item["code"] == "MATCH_CONFLICT"
    db = SessionLocal()
    try:
        unchanged = db.get(User, employee_user_id)
        assert unchanged.auth_source == "local"
        assert unchanged.ldap_external_id is None
    finally:
        db.close()


@pytest.mark.parametrize("state", ["unlinked", "linked"])
def test_bind_only_accepts_the_suggested_existing_user(client, monkeypatch, state):
    _configure(client)
    external_id = str(uuid4())
    db = SessionLocal()
    target = User(
        username=f"bind_target_{uuid4().hex[:8]}", full_name="Bind Target",
        password_hash=get_password_hash("test-only-password"), is_active=True,
        must_change_password=False, deleted=0,
    )
    if state == "linked":
        target.auth_source = "ldap"
        target.ldap_external_id = external_id
    db.add(target)
    db.commit()
    target_id = target.id
    original_name = target.full_name
    db.close()
    entry = _directory_user(external_id)
    monkeypatch.setattr(
        "app.services.ldap_sync_service.ldap_client.search_user_by_external_id",
        lambda *_args: entry,
    )

    response = client.post(
        "/api/v1/admin/ldap/sync",
        json={"items": [{"external_id": external_id, "decision": "bind", "user_id": target_id}]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["status"] == "failed"
    db = SessionLocal()
    try:
        assert db.get(User, target_id).full_name == original_name
    finally:
        db.close()


def test_unique_identity_race_isolated_by_savepoint_and_later_item_continues(client, monkeypatch):
    _configure(client)
    first_id, racing_id, later_id = str(uuid4()), str(uuid4()), str(uuid4())
    duplicate_employee_no = f"E-RACE-{uuid4().hex[:6]}"
    entries = {
        first_id: _directory_user(first_id, employee_no=duplicate_employee_no),
        racing_id: _directory_user(racing_id, employee_no=duplicate_employee_no),
        later_id: _directory_user(later_id),
    }
    monkeypatch.setattr(
        "app.services.ldap_sync_service.ldap_client.search_user_by_external_id",
        lambda _config, _password, external_id: entries[external_id],
    )
    monkeypatch.setattr(
        "app.services.ldap_sync_service.match_directory_user",
        lambda _db, entry: {**entry, "sync_status": "unlinked", "matched_user": None, "conflict_reason": None},
    )

    response = client.post(
        "/api/v1/admin/ldap/sync",
        json={"items": [
            {"external_id": first_id, "decision": "create"},
            {"external_id": racing_id, "decision": "create"},
            {"external_id": later_id, "decision": "create"},
        ]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["status"] for item in body["items"]] == ["created", "failed", "created"]
    assert body["items"][1]["code"] == "IDENTITY_CONFLICT"
    assert body["summary"]["created"] == 2
    assert body["summary"]["failed"] == 1


def test_ldap_query_failure_preserves_linked_user_and_is_audited(client, monkeypatch):
    from app.services.ldap_client import LdapNetworkError

    _configure(client)
    external_id = str(uuid4())
    db = SessionLocal()
    linked = User(
        username=f"query_fail_{uuid4().hex[:8]}", full_name="Before Failure",
        department="Original", password_hash=get_password_hash("test-only-password"),
        auth_source="ldap", ldap_external_id=external_id, is_active=True,
        must_change_password=False, deleted=0,
    )
    db.add(linked)
    db.commit()
    linked_id = linked.id
    db.close()

    def fail_query(*_args):
        raise LdapNetworkError("LDAP 服务器不可达")

    monkeypatch.setattr("app.services.ldap_sync_service.ldap_client.search_user_by_external_id", fail_query)
    response = client.post(
        "/api/v1/admin/ldap/sync",
        json={"items": [{"external_id": external_id, "decision": "update"}]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"][0]["status"] == "failed"
    assert body["items"][0]["code"] == "LDAP_QUERY_FAILED"

    db = SessionLocal()
    try:
        unchanged = db.get(User, linked_id)
        assert unchanged.is_active is True
        assert unchanged.full_name == "Before Failure"
        assert unchanged.department == "Original"
        run = db.get(LdapSyncRun, body["run_id"])
        audit_item = db.query(LdapSyncItem).filter(LdapSyncItem.run_id == run.id).one()
        assert run.status == "partial_failed"
        assert run.failed_count == 1
        assert audit_item.status == "failed"
        assert audit_item.message == "LDAP 服务器不可达"
    finally:
        db.close()


def test_two_ad_identities_cannot_bind_the_same_sdlc_user(client, monkeypatch):
    _configure(client)
    first_id, second_id = str(uuid4()), str(uuid4())
    employee_no = f"E-SAME-{uuid4().hex[:6]}"
    db = SessionLocal()
    target = User(
        username=f"same_target_{uuid4().hex[:8]}", full_name="Same Target",
        employee_no=employee_no, password_hash=get_password_hash("test-only-password"),
        is_active=True, must_change_password=False, deleted=0,
    )
    db.add(target)
    db.commit()
    target_id = target.id
    db.close()
    entries = {
        first_id: _directory_user(first_id, employee_no=employee_no),
        second_id: _directory_user(second_id, employee_no=employee_no),
    }
    monkeypatch.setattr(
        "app.services.ldap_sync_service.ldap_client.search_user_by_external_id",
        lambda _config, _password, external_id: entries[external_id],
    )

    response = client.post(
        "/api/v1/admin/ldap/sync",
        json={"items": [
            {"external_id": first_id, "decision": "bind", "user_id": target_id},
            {"external_id": second_id, "decision": "bind", "user_id": target_id},
        ]},
    )

    assert response.status_code == 200, response.text
    assert [item["status"] for item in response.json()["items"]] == ["bound", "failed"]
    assert response.json()["items"][1]["code"] == "MATCH_CONFLICT"
    db = SessionLocal()
    try:
        assert db.get(User, target_id).ldap_external_id == first_id
    finally:
        db.close()


def test_uppercase_uuid_selection_matches_lowercase_directory_identity(client, monkeypatch):
    _configure(client)
    canonical_id = str(uuid4())
    entry = _directory_user(canonical_id)
    monkeypatch.setattr(
        "app.services.ldap_sync_service.ldap_client.search_user_by_external_id",
        lambda *_args: entry,
    )

    response = client.post(
        "/api/v1/admin/ldap/sync",
        json={"items": [{"external_id": canonical_id.upper(), "decision": "create"}]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["status"] == "created"
    db = SessionLocal()
    try:
        assert db.query(User).filter(User.ldap_external_id == canonical_id).one()
    finally:
        db.close()


@pytest.mark.parametrize("readiness", ["disabled", "stale"])
def test_sync_rejects_config_that_is_not_enabled_and_currently_tested(client, monkeypatch, readiness):
    settings.__dict__["integration_encryption_key"] = Fernet.generate_key().decode()
    assert client.put("/api/v1/admin/ldap", json=_payload(enabled=False)).status_code == 200
    if readiness == "stale":
        from app.models.ldap_integration import LdapIntegrationConfig
        from app.services.ldap_config_service import _fingerprint

        db = SessionLocal()
        config = db.get(LdapIntegrationConfig, 1)
        config.tested_fingerprint = _fingerprint(config)
        config.enabled = True
        config.host = "stale-sync.example.com"
        db.commit()
        db.close()
    monkeypatch.setattr(
        "app.services.ldap_sync_service.ldap_client.search_user_by_external_id",
        lambda *_args: pytest.fail("unready config must not query LDAP"),
    )

    response = client.post(
        "/api/v1/admin/ldap/sync",
        json={"items": [{"external_id": str(uuid4()), "decision": "create"}]},
    )

    assert response.status_code == 409

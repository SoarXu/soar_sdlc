from cryptography.fernet import Fernet

from app.core.config import settings
from app.services.ldap_client import LdapSearchResult

from test_ldap_config_api import _payload
import pytest


def _mark_config_ready():
    from app.db.session import SessionLocal
    from app.models.ldap_integration import LdapIntegrationConfig
    from app.services.ldap_config_service import _fingerprint

    db = SessionLocal()
    config = db.get(LdapIntegrationConfig, 1)
    config.tested_fingerprint = _fingerprint(config)
    config.enabled = True
    db.commit()
    db.close()


def test_directory_users_returns_only_mapped_fields(client, monkeypatch):
    settings.__dict__["integration_encryption_key"] = Fernet.generate_key().decode()
    assert client.put("/api/v1/admin/ldap", json=_payload()).status_code == 200
    _mark_config_ready()

    def fake_search(*_args, **_kwargs):
        return LdapSearchResult(
            items=[{
                "username": "alice", "employee_no": "E001", "full_name": "Alice",
                "email": "alice@example.com", "mobile": None, "department": "R&D",
                "external_id": "guid-1", "dn": "CN=Alice,DC=example,DC=com", "enabled": True,
            }],
            next_cursor=None,
        )

    monkeypatch.setattr("app.services.ldap_config_service.ldap_client.search_users", fake_search)
    response = client.get("/api/v1/admin/ldap/directory-users?q=ali&page_size=20")
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [{
        "username": "alice", "employee_no": "E001", "full_name": "Alice",
        "email": "alice@example.com", "mobile": None, "department": "R&D",
        "external_id": "guid-1", "dn": "CN=Alice,DC=example,DC=com", "enabled": True,
        "sync_status": "unlinked", "matched_user": None, "conflict_reason": None,
    }], "page_size": 20, "next_cursor": None}


def test_directory_users_passes_runtime_query_scope_without_saving_config(client, monkeypatch):
    settings.__dict__["integration_encryption_key"] = Fernet.generate_key().decode()
    assert client.put("/api/v1/admin/ldap", json=_payload()).status_code == 200
    _mark_config_ready()
    calls = []

    def fake_search(*_args, **kwargs):
        calls.append(kwargs)
        return LdapSearchResult(items=[], next_cursor=None)

    monkeypatch.setattr("app.services.ldap_config_service.ldap_client.search_users", fake_search)
    response = client.get(
        "/api/v1/admin/ldap/directory-users",
        params={
            "user_base_dn": "OU=Contractors,DC=example,DC=com",
            "exclude_disabled": False,
            "page_size": 30,
        },
    )

    assert response.status_code == 200, response.text
    assert calls[0]["user_base_dn"] == "OU=Contractors,DC=example,DC=com"
    assert calls[0]["exclude_disabled"] is False
    assert calls[0]["page_size"] == 30


def test_non_admin_cannot_read_ldap_config(client):
    from app.core.security import create_access_token

    response = client.get(
        "/api/v1/admin/ldap",
        headers={"Authorization": f"Bearer {create_access_token('bob')}"},
    )
    assert response.status_code == 403


def test_directory_users_rejects_invalid_cursor(client):
    settings.__dict__["integration_encryption_key"] = Fernet.generate_key().decode()
    assert client.put("/api/v1/admin/ldap", json=_payload()).status_code == 200
    _mark_config_ready()
    response = client.get("/api/v1/admin/ldap/directory-users?cursor=not%2Bbase64%21&page_size=20")
    assert response.status_code == 422


def test_disabled_config_rejects_directory_query_without_contacting_ldap(client, monkeypatch):
    settings.__dict__["integration_encryption_key"] = Fernet.generate_key().decode()
    assert client.put("/api/v1/admin/ldap", json=_payload(enabled=False)).status_code == 200
    monkeypatch.setattr(
        "app.services.ldap_config_service.ldap_client.search_users",
        lambda *_args, **_kwargs: pytest.fail("disabled config must not query LDAP"),
    )
    response = client.get("/api/v1/admin/ldap/directory-users")
    assert response.status_code == 409


def test_stale_test_fingerprint_rejects_directory_query(client, monkeypatch):
    settings.__dict__["integration_encryption_key"] = Fernet.generate_key().decode()
    assert client.put("/api/v1/admin/ldap", json=_payload()).status_code == 200
    _mark_config_ready()
    from app.db.session import SessionLocal
    from app.models.ldap_integration import LdapIntegrationConfig

    db = SessionLocal()
    config = db.get(LdapIntegrationConfig, 1)
    config.host = "changed.example.com"
    db.commit()
    db.close()
    monkeypatch.setattr(
        "app.services.ldap_config_service.ldap_client.search_users",
        lambda *_args, **_kwargs: pytest.fail("stale config must not query LDAP"),
    )
    response = client.get("/api/v1/admin/ldap/directory-users")
    assert response.status_code == 409


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("put", "/api/v1/admin/ldap", {"json": _payload()}),
        ("post", "/api/v1/admin/ldap/test", {}),
        ("get", "/api/v1/admin/ldap/directory-users", {}),
    ],
)
def test_non_admin_cannot_mutate_test_or_query_ldap(client, method, path, kwargs):
    from app.core.security import create_access_token

    response = getattr(client, method)(
        path,
        headers={"Authorization": f"Bearer {create_access_token('bob')}"},
        **kwargs,
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("get", "/api/v1/admin/ldap", {}),
        ("put", "/api/v1/admin/ldap", {"json": _payload()}),
        ("post", "/api/v1/admin/ldap/test", {}),
        ("get", "/api/v1/admin/ldap/directory-users", {}),
    ],
)
def test_anonymous_cannot_access_ldap_admin_endpoints(client, method, path, kwargs):
    response = getattr(client, method)(path, headers={"X-Test-No-Auth": "1"}, **kwargs)
    assert response.status_code == 401

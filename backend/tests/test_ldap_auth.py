from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from jose import jwt

from app.controllers import auth_controller
from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.user import User
from app.services import ldap_auth_service
from app.services.ldap_auth_service import (
    LdapCredentialsRejected,
    LdapDirectoryUnavailable,
    LdapUserAuthenticator,
)
from app.services.user_service import authenticate_user


class RecordingAuthenticator:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls = []

    def authenticate(self, config, user_dn: str, password: str) -> None:
        self.calls.append((config, user_dn, password))
        if self.error:
            raise self.error


@pytest.fixture()
def ldap_user():
    username = f"ldap_login_{uuid4().hex[:8]}"
    db = SessionLocal()
    user = User(
        username=username,
        full_name="LDAP Login User",
        password_hash=get_password_hash("must-not-be-used"),
        auth_source="ldap",
        ldap_external_id=str(uuid4()),
        ldap_dn=f"CN={username},OU=Employees,DC=example,DC=com",
        is_active=True,
        must_change_password=False,
        deleted=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        yield db, user
    finally:
        db.delete(user)
        db.commit()
        db.close()


@pytest.fixture()
def local_user():
    username = f"local_login_{uuid4().hex[:8]}"
    db = SessionLocal()
    user = User(
        username=username,
        full_name="Local Login User",
        password_hash=get_password_hash("local-secret"),
        auth_source="local",
        is_active=True,
        is_system_admin=True,
        must_change_password=False,
        deleted=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        yield db, user
    finally:
        db.delete(user)
        db.commit()
        db.close()


def test_local_user_uses_hash_without_calling_ldap(local_user):
    db, user = local_user
    authenticator = RecordingAuthenticator(error=AssertionError("LDAP must not be called"))

    result = authenticate_user(db, user.username, "local-secret", ldap_authenticator=authenticator)

    assert result.id == user.id
    assert authenticator.calls == []


def test_ldap_user_binds_with_saved_dn_and_submitted_password(ldap_user, monkeypatch):
    db, user = ldap_user
    ready_config = SimpleNamespace(enabled=True, tested_fingerprint="ready")
    monkeypatch.setattr("app.services.ldap_auth_service.require_ready_config", lambda _db: ready_config)
    authenticator = RecordingAuthenticator()

    result = authenticate_user(db, user.username, "submitted-secret", ldap_authenticator=authenticator)

    assert result.id == user.id
    assert authenticator.calls == [(ready_config, user.ldap_dn, "submitted-secret")]


def test_successful_ldap_authentication_persists_last_login_time(ldap_user, monkeypatch):
    db, user = ldap_user
    monkeypatch.setattr("app.services.ldap_auth_service.require_ready_config", lambda _db: SimpleNamespace())

    assert user.last_login_time is None
    result = authenticate_user(db, user.username, "submitted-secret", ldap_authenticator=RecordingAuthenticator())
    db.expire_all()

    assert result.last_login_time is not None
    assert db.query(User).filter(User.id == user.id).one().last_login_time is not None


def test_ldap_credentials_are_rejected_without_local_password_fallback(ldap_user, monkeypatch):
    db, user = ldap_user
    monkeypatch.setattr("app.services.ldap_auth_service.require_ready_config", lambda _db: SimpleNamespace())
    authenticator = RecordingAuthenticator(error=LdapCredentialsRejected())

    assert authenticate_user(db, user.username, "must-not-be-used", ldap_authenticator=authenticator) is None
    db.expire_all()
    assert db.query(User).filter(User.id == user.id).one().last_login_time is None


def test_ldap_user_requires_complete_synced_identity(ldap_user):
    db, user = ldap_user
    user.ldap_dn = None
    db.commit()
    authenticator = RecordingAuthenticator()

    assert authenticate_user(db, user.username, "anything", ldap_authenticator=authenticator) is None
    assert authenticator.calls == []


def test_directory_failure_is_not_converted_to_bad_credentials(ldap_user, monkeypatch):
    db, user = ldap_user
    monkeypatch.setattr("app.services.ldap_auth_service.require_ready_config", lambda _db: SimpleNamespace())
    authenticator = RecordingAuthenticator(error=LdapDirectoryUnavailable())

    with pytest.raises(LdapDirectoryUnavailable):
        authenticate_user(db, user.username, "secret", ldap_authenticator=authenticator)


def test_login_returns_503_for_directory_failure(client, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise LdapDirectoryUnavailable()

    monkeypatch.setattr(auth_controller, "authenticate_user", unavailable)
    response = client.post("/api/v1/auth/login", json={"username": "ldap-user", "password": "secret"})

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "LDAP_DIRECTORY_UNAVAILABLE",
        "message": "目录服务暂时不可用",
    }


def test_ldap_login_token_is_limited_to_eight_hours(client, monkeypatch):
    user = SimpleNamespace(
        id=987654,
        username="ldap-token-user",
        full_name="LDAP Token User",
        must_change_password=False,
        auth_source="ldap",
    )
    monkeypatch.setattr(auth_controller, "authenticate_user", lambda *_args, **_kwargs: user)

    response = client.post("/api/v1/auth/login", json={"username": user.username, "password": "secret"})

    payload = jwt.decode(response.json()["access_token"], settings.secret_key, algorithms=[ALGORITHM])
    issued_window = datetime.fromtimestamp(payload["exp"], tz=timezone.utc) - datetime.now(timezone.utc)
    assert response.status_code == 200
    assert issued_window.total_seconds() <= 8 * 60 * 60
    assert issued_window.total_seconds() > 7.9 * 60 * 60


def test_ldap_user_cannot_change_or_reset_password(client, ldap_user):
    _db, user = ldap_user
    user_token = create_access_token(user.username)

    changed = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "anything", "new_password": "NewPassword123!"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    reset = client.post(f"/api/v1/users/{user.id}/reset-password")

    assert changed.status_code == 403
    assert reset.status_code == 403
    assert changed.json()["detail"]["code"] == "LDAP_PASSWORD_MANAGED_EXTERNALLY"
    assert reset.json()["detail"]["code"] == "LDAP_PASSWORD_MANAGED_EXTERNALLY"


def test_starttls_authentication_opens_upgrades_then_binds(monkeypatch):
    calls = []

    class FakeConnection:
        def open(self):
            calls.append("open")
            return True

        def start_tls(self):
            calls.append("start_tls")
            return True

        def bind(self):
            calls.append("bind")
            return True

    monkeypatch.setattr(ldap_auth_service, "Tls", lambda **_kwargs: object())
    monkeypatch.setattr(ldap_auth_service, "Server", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(ldap_auth_service, "Connection", lambda *_args, **_kwargs: FakeConnection())
    config = SimpleNamespace(protocol="ldap", host="dc.example.com", port=389, connect_timeout=7)

    connection = LdapUserAuthenticator._create_connection(config, "CN=User,DC=example,DC=com", "secret")

    assert isinstance(connection, FakeConnection)
    assert calls == ["open", "start_tls", "bind"]


def test_ldaps_authentication_uses_user_dn_password_and_tls_settings(monkeypatch):
    captured = {}

    class FakeConnection:
        pass

    def server_factory(host, **kwargs):
        captured["server"] = (host, kwargs)
        return object()

    def connection_factory(server, **kwargs):
        captured["connection"] = (server, kwargs)
        return FakeConnection()

    monkeypatch.setattr(ldap_auth_service, "Tls", lambda **kwargs: ("tls", kwargs))
    monkeypatch.setattr(ldap_auth_service, "Server", server_factory)
    monkeypatch.setattr(ldap_auth_service, "Connection", connection_factory)
    config = SimpleNamespace(protocol="ldaps", host="dc.example.com", port=636, connect_timeout=9)

    LdapUserAuthenticator._create_connection(config, "CN=User,DC=example,DC=com", "submitted-secret")

    assert captured["server"][0] == "dc.example.com"
    assert captured["server"][1]["use_ssl"] is True
    assert captured["server"][1]["connect_timeout"] == 9
    assert captured["connection"][1]["user"] == "CN=User,DC=example,DC=com"
    assert captured["connection"][1]["password"] == "submitted-secret"
    assert captured["connection"][1]["auto_bind"] is True
    assert captured["connection"][1]["receive_timeout"] == 9

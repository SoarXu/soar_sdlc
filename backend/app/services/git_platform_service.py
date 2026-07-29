import json
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cryptography.fernet import InvalidToken
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import SecretConfigurationError, decrypt_secret, encrypt_secret
from app.models.devops import DevopsGitPlatformConnection
from app.views.devops_view import DevopsGitPlatformConnectionCreate


def list_connections(db: Session) -> list[dict]:
    connections = (
        db.query(DevopsGitPlatformConnection)
        .filter(DevopsGitPlatformConnection.deleted == 0)
        .order_by(DevopsGitPlatformConnection.id.desc())
        .all()
    )
    return [_connection_to_dict(item) for item in connections]


def create_connection(db: Session, payload: DevopsGitPlatformConnectionCreate) -> dict:
    if db.query(DevopsGitPlatformConnection).filter(DevopsGitPlatformConnection.name == payload.name.strip()).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Git platform connection name already exists")

    connection = DevopsGitPlatformConnection(
        name=payload.name.strip(),
        provider=payload.provider,
        base_url=_normalize_base_url(payload.base_url),
        access_token_encrypted=_encrypt_access_token(payload.access_token),
        enabled=payload.enabled,
        connection_status="pending",
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return _connection_to_dict(connection)


def test_connection(db: Session, connection_id: int) -> dict:
    connection = _get_connection(db, connection_id)
    connection.last_verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        connection.authenticated_username = _fetch_authenticated_username(connection)
        connection.connection_status = "connected"
        connection.last_error = None
    except GitPlatformConnectionError as error:
        connection.connection_status = "failed"
        connection.last_error = str(error)
    db.commit()
    db.refresh(connection)
    return _connection_to_dict(connection)


def update_connection(db: Session, connection_id: int, payload) -> dict:
    connection = _get_connection(db, connection_id)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        name = changes["name"].strip()
        duplicate = (
            db.query(DevopsGitPlatformConnection)
            .filter(
                DevopsGitPlatformConnection.name == name,
                DevopsGitPlatformConnection.id != connection_id,
                DevopsGitPlatformConnection.deleted == 0,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Git platform connection name already exists")
        connection.name = name
    verification_invalidated = False
    if "provider" in changes and changes["provider"] is not None and changes["provider"] != connection.provider:
        connection.provider = changes["provider"]
        verification_invalidated = True
    if "base_url" in changes and changes["base_url"] is not None:
        base_url = _normalize_base_url(changes["base_url"])
        if base_url != connection.base_url:
            connection.base_url = base_url
            verification_invalidated = True
    if "enabled" in changes and changes["enabled"] is not None:
        connection.enabled = changes["enabled"]
    token = changes.get("access_token")
    if token and token.strip():
        connection.access_token_encrypted = _encrypt_access_token(token.strip())
        verification_invalidated = True
    if verification_invalidated:
        _reset_verification(connection)
    db.commit()
    db.refresh(connection)
    return _connection_to_dict(connection)


def delete_connection(db: Session, connection_id: int) -> None:
    connection = _get_connection(db, connection_id)
    connection.deleted = 1
    connection.delete_time = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()


def _fetch_authenticated_username(connection: DevopsGitPlatformConnection) -> str:
    try:
        token = decrypt_secret(connection.access_token_encrypted or "")
    except (InvalidToken, SecretConfigurationError):
        raise GitPlatformConnectionError("Stored Git token cannot be decrypted") from None
    profile_path, headers, username_field = _provider_request_details(connection.provider, token)
    request = Request(f"{connection.base_url.rstrip('/')}{profile_path}", headers=headers)
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise GitPlatformConnectionError(f"Authentication failed (HTTP {error.code})") from error
    except URLError:
        raise GitPlatformConnectionError("Could not reach the Git platform") from None
    except (OSError, ValueError, json.JSONDecodeError):
        raise GitPlatformConnectionError("Git platform returned an invalid response") from None

    username = payload.get(username_field)
    if not username:
        raise GitPlatformConnectionError("Git platform response did not include an account name")
    return str(username)


def _provider_request_details(provider: str, token: str) -> tuple[str, dict[str, str], str]:
    details = {
        "gitea": ("/api/v1/user", {"Authorization": f"token {token}"}, "login"),
        "gitlab": ("/api/v4/user", {"PRIVATE-TOKEN": token}, "username"),
        "github": (
            "/user",
            {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            "login",
        ),
    }
    return details[provider]


def _get_connection(db: Session, connection_id: int) -> DevopsGitPlatformConnection:
    connection = (
        db.query(DevopsGitPlatformConnection)
        .filter(DevopsGitPlatformConnection.id == connection_id, DevopsGitPlatformConnection.deleted == 0)
        .first()
    )
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Git platform connection not found")
    return connection


def _normalize_base_url(value: str) -> str:
    base_url = value.strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Git platform URL must be an absolute HTTP(S) URL")
    return base_url


def _encrypt_access_token(value: str) -> str:
    try:
        return encrypt_secret(value)
    except SecretConfigurationError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


def _reset_verification(connection: DevopsGitPlatformConnection) -> None:
    connection.connection_status = "pending"
    connection.authenticated_username = None
    connection.last_verified_at = None
    connection.last_error = None


class GitPlatformConnectionError(Exception):
    pass


def _connection_to_dict(connection: DevopsGitPlatformConnection) -> dict:
    return {
        "id": connection.id,
        "name": connection.name,
        "provider": connection.provider,
        "base_url": connection.base_url,
        "enabled": connection.enabled,
        "has_access_token": bool(connection.access_token_encrypted),
        "authenticated_username": connection.authenticated_username,
        "connection_status": connection.connection_status,
        "last_verified_at": connection.last_verified_at,
        "last_error": connection.last_error,
        "create_time": connection.create_time,
        "update_time": connection.update_time,
    }

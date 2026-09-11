import hashlib
import json
from datetime import datetime, timezone

from cryptography.fernet import InvalidToken
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import SecretConfigurationError, decrypt_integration_secret, encrypt_integration_secret
from app.models.ldap_integration import LdapIntegrationConfig
from app.services.ldap_client import LdapConnectionError, LdapQueryError, ldap_client
from app.services.ldap_sync_service import match_directory_user


CONFIG_FIELDS = (
    "protocol", "host", "port", "connect_timeout", "base_dn", "bind_username",
    "user_base_dn", "user_filter", "exclude_disabled", "page_size",
    "username_attribute", "employee_no_attribute", "full_name_attribute",
    "email_attribute", "mobile_attribute", "department_attribute", "external_id_attribute",
)
CONNECTION_IDENTITY_FIELDS = ("protocol", "host", "port", "bind_username")


def get_config(db: Session) -> dict:
    config = _get_config(db)
    if config is None:
        return _defaults()
    return _to_dict(config)


def save_config(db: Session, payload) -> dict:
    config = _get_config(db)
    password = payload.bind_password
    has_password = bool(password and password.strip())
    if config is None and not has_password:
        raise HTTPException(status_code=422, detail="首次保存 LDAP 配置时必须填写绑定密码")
    if config is not None and not has_password and any(
        getattr(config, field) != getattr(payload, field) for field in CONNECTION_IDENTITY_FIELDS
    ):
        raise HTTPException(status_code=422, detail="修改 LDAP 连接身份配置时必须重新填写绑定密码")
    if config is None:
        config = LdapIntegrationConfig(id=1)
        db.add(config)

    for field in CONFIG_FIELDS:
        setattr(config, field, getattr(payload, field))
    if has_password:
        try:
            config.bind_password_encrypted = encrypt_integration_secret(password)
        except SecretConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    current_fingerprint = _fingerprint(config)
    if payload.enabled and config.tested_fingerprint != current_fingerprint:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="LDAP 配置必须成功测试且未发生变化后才能启用")
    config.enabled = payload.enabled
    db.commit()
    db.refresh(config)
    return _to_dict(config)


def test_config(db: Session) -> dict:
    config = _require_config(db)
    password = _password(config)
    try:
        count = ldap_client.test_connection(config, password)
    except (LdapConnectionError, LdapQueryError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    config.tested_fingerprint = _fingerprint(config)
    config.tested_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"success": True, "message": "LDAP 连接及用户查询测试成功", "sampled_users": count, "tested_at": config.tested_at}


def directory_users(
    db: Session,
    query: str | None,
    cursor: str | None,
    page_size: int,
    user_base_dn: str | None = None,
    exclude_disabled: bool | None = None,
) -> dict:
    config = require_ready_config(db)
    try:
        result = ldap_client.search_users(
            config,
            _password(config),
            query=query,
            cursor=cursor,
            page_size=page_size,
            user_base_dn=user_base_dn,
            exclude_disabled=exclude_disabled,
        )
    except LdapQueryError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except LdapConnectionError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {
        "items": [match_directory_user(db, item) for item in result.items],
        "page_size": page_size,
        "next_cursor": result.next_cursor,
        "total": result.total,
    }


def _get_config(db: Session):
    return db.query(LdapIntegrationConfig).filter(LdapIntegrationConfig.id == 1).first()


def _require_config(db: Session):
    config = _get_config(db)
    if config is None:
        raise HTTPException(status_code=404, detail="尚未配置 LDAP 集成")
    return config


def require_ready_config(db: Session):
    config = _require_config(db)
    if not config.enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="LDAP 集成尚未启用")
    if config.tested_fingerprint != _fingerprint(config):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="LDAP 配置尚未测试或测试后已发生变化")
    return config


def _password(config) -> str:
    try:
        return decrypt_integration_secret(config.bind_password_encrypted)
    except (InvalidToken, SecretConfigurationError) as error:
        raise HTTPException(status_code=503, detail="LDAP 绑定密码无法解密，请检查 INTEGRATION_ENCRYPTION_KEY") from error


def _fingerprint(config) -> str:
    data = {field: getattr(config, field) for field in CONFIG_FIELDS}
    data["bind_password_encrypted"] = config.bind_password_encrypted
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _to_dict(config) -> dict:
    result = {field: getattr(config, field) for field in CONFIG_FIELDS}
    result.update({
        "enabled": bool(config.enabled),
        "has_bind_password": bool(config.bind_password_encrypted),
        "tested_at": config.tested_at,
        "configuration_tested": config.tested_fingerprint == _fingerprint(config),
    })
    return result


def _defaults() -> dict:
    return {
        "enabled": False, "protocol": "ldaps", "host": "", "port": 636,
        "connect_timeout": 5, "base_dn": "", "bind_username": "",
        "has_bind_password": False, "user_base_dn": None,
        "user_filter": "(&(objectCategory=person)(objectClass=user))",
        "exclude_disabled": True, "page_size": 50,
        "username_attribute": "sAMAccountName", "employee_no_attribute": "employeeID",
        "full_name_attribute": "displayName", "email_attribute": "mail",
        "mobile_attribute": "mobile", "department_attribute": "department",
        "external_id_attribute": "objectGUID", "tested_at": None, "configuration_tested": False,
    }

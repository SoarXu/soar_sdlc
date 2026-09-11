from cryptography.fernet import Fernet

from app.core.config import settings
from app.db.session import SessionLocal


def _payload(**overrides):
    payload = {
        "enabled": False,
        "protocol": "ldaps",
        "host": "dc.example.com",
        "port": 636,
        "connect_timeout": 5,
        "base_dn": "DC=example,DC=com",
        "bind_username": "svc@example.com",
        "bind_password": "bind-secret",
        "user_base_dn": "OU=Employees,DC=example,DC=com",
        "user_filter": "(&(objectCategory=person)(objectClass=user))",
        "exclude_disabled": True,
        "page_size": 50,
        "username_attribute": "sAMAccountName",
        "employee_no_attribute": "employeeID",
        "full_name_attribute": "displayName",
        "email_attribute": "mail",
        "mobile_attribute": "mobile",
        "department_attribute": "department",
        "external_id_attribute": "objectGUID",
    }
    payload.update(overrides)
    return payload


def test_admin_can_save_and_read_masked_ldap_config(client):
    key = Fernet.generate_key().decode()
    settings.__dict__["integration_encryption_key"] = key

    saved = client.put("/api/v1/admin/ldap", json=_payload())
    assert saved.status_code == 200, saved.text
    assert saved.json()["has_bind_password"] is True
    assert "bind_password" not in saved.json()

    loaded = client.get("/api/v1/admin/ldap")
    assert loaded.status_code == 200
    assert loaded.json()["host"] == "dc.example.com"
    assert "bind_password_encrypted" not in loaded.json()

    db = SessionLocal()
    try:
        encrypted = db.execute(__import__("sqlalchemy").text("select bind_password_encrypted from ldap_integration_config limit 1")).scalar_one()
    finally:
        db.close()
    assert encrypted != "bind-secret"
    assert Fernet(key.encode()).decrypt(encrypted.encode()).decode() == "bind-secret"


def test_edit_with_blank_password_keeps_existing_secret(client):
    settings.__dict__["integration_encryption_key"] = Fernet.generate_key().decode()
    assert client.put("/api/v1/admin/ldap", json=_payload()).status_code == 200
    updated = client.put(
        "/api/v1/admin/ldap",
        json=_payload(user_base_dn="OU=Engineering,DC=example,DC=com", bind_password=""),
    )
    assert updated.status_code == 200
    assert updated.json()["has_bind_password"] is True


def test_first_save_requires_bind_password(client):
    from app.models.ldap_integration import LdapIntegrationConfig

    db = SessionLocal()
    try:
        db.query(LdapIntegrationConfig).delete()
        db.commit()
    finally:
        db.close()
    response = client.put("/api/v1/admin/ldap", json=_payload(bind_password=""))
    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "首次保存LDAP配置时必须填写绑定密码"


def test_changed_config_cannot_be_enabled_until_successfully_tested(client):
    settings.__dict__["integration_encryption_key"] = Fernet.generate_key().decode()
    assert client.put("/api/v1/admin/ldap", json=_payload()).status_code == 200
    response = client.put("/api/v1/admin/ldap", json=_payload(enabled=True, bind_password=""))
    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "LDAP配置必须成功测试且未发生变化后才能启用"


def test_attribute_mapping_rejects_ldap_filter_syntax(client):
    settings.__dict__["integration_encryption_key"] = Fernet.generate_key().decode()
    response = client.put(
        "/api/v1/admin/ldap",
        json=_payload(username_attribute="sAMAccountName)(objectClass=*)"),
    )
    assert response.status_code == 422


def test_existing_git_secret_helpers_accept_generic_integration_key():
    from app.core.security import decrypt_secret, encrypt_secret

    settings.__dict__["git_platform_encryption_key"] = ""
    settings.__dict__["integration_encryption_key"] = Fernet.generate_key().decode()
    encrypted = encrypt_secret("legacy-compatible")
    assert decrypt_secret(encrypted) == "legacy-compatible"


def test_connection_identity_change_requires_new_bind_password(client):
    settings.__dict__["integration_encryption_key"] = Fernet.generate_key().decode()
    assert client.put("/api/v1/admin/ldap", json=_payload()).status_code == 200

    response = client.put(
        "/api/v1/admin/ldap",
        json=_payload(host="attacker.example.com", bind_password=""),
    )

    assert response.status_code == 422
    assert "绑定密码" in response.json()["detail"]["message"]


def test_ldap_host_rejects_urls_and_embedded_credentials(client):
    settings.__dict__["integration_encryption_key"] = Fernet.generate_key().decode()
    for host in ("ldaps://dc.example.com", "user@dc.example.com", "dc.example.com/path", "dc.example.com:636"):
        response = client.put("/api/v1/admin/ldap", json=_payload(host=host))
        assert response.status_code == 422, host

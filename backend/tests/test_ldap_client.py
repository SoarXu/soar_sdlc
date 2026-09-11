from types import SimpleNamespace

import pytest
from ldap3.core.exceptions import (
    LDAPBindError,
    LDAPInsufficientAccessRightsResult,
    LDAPInvalidFilterError,
    LDAPSocketOpenError,
    LDAPStartTLSError,
)


def _entry(**attributes):
    return SimpleNamespace(entry_attributes_as_dict=attributes)


def test_search_users_maps_whitelisted_ad_attributes_and_paged_cookie():
    from app.services.ldap_client import LdapClient

    connection = SimpleNamespace(
        entries=[
            _entry(
                sAMAccountName=["alice"],
                employeeID=["E001"],
                displayName=["Alice Zhang"],
                mail=["alice@example.com"],
                mobile=["13800000000"],
                department=["R&D"],
                objectGUID=[b"\x33\x22\x11\x00\x55\x44\x77\x66\x88\x99\xaa\xbb\xcc\xdd\xee\xff"],
                userAccountControl=[512],
                secretAttribute=["must-not-leak"],
            )
        ],
        result={"controls": {"1.2.840.113556.1.4.319": {"value": {"cookie": b"next"}}}},
    )
    connection.search = lambda **_kwargs: True
    client = LdapClient(connection_factory=lambda _config, _password: connection)

    result = client.search_users(_config(), "secret", query="ali", page_size=20)

    assert result.items == [
        {
            "username": "alice",
            "employee_no": "E001",
            "full_name": "Alice Zhang",
            "email": "alice@example.com",
            "mobile": "13800000000",
            "department": "R&D",
            "external_id": "00112233-4455-6677-8899-aabbccddeeff",
            "dn": None,
            "enabled": True,
        }
    ]
    assert result.next_cursor == "bmV4dA"


def test_search_users_accepts_runtime_scope_and_disabled_account_option():
    from app.services.ldap_client import LdapClient

    calls = []
    connection = SimpleNamespace(entries=[], result={})
    connection.search = lambda **kwargs: calls.append(kwargs) or True

    LdapClient(connection_factory=lambda *_args: connection).search_users(
        _config(),
        "secret",
        user_base_dn="OU=Contractors,DC=example,DC=com",
        exclude_disabled=False,
    )

    assert calls[0]["search_base"] == "OU=Contractors,DC=example,DC=com"
    assert calls[0]["search_filter"] == "(&(&(objectCategory=person)(objectClass=user)))"


def test_search_users_rejects_unsafe_query_without_contacting_directory():
    from app.services.ldap_client import LdapClient, LdapQueryError

    client = LdapClient(connection_factory=lambda *_args: pytest.fail("must not connect"))
    with pytest.raises(LdapQueryError, match="搜索关键字包含非法字符"):
        client.search_users(_config(), "secret", query="*)(uid=*)")


def test_unbind_failure_does_not_override_successful_search():
    from app.services.ldap_client import LdapClient

    class Connection:
        entries = []
        result = {}

        def search(self, **_kwargs):
            return True

        def unbind(self):
            raise RuntimeError("unbind failed")

    result = LdapClient(connection_factory=lambda *_args: Connection()).search_users(_config(), "secret")
    assert result.items == []


def test_unbind_failure_does_not_override_stable_query_error():
    from app.services.ldap_client import LdapClient, LdapQueryError

    class Connection:
        entries = []
        result = {}

        def search(self, **_kwargs):
            return False

        def unbind(self):
            raise RuntimeError("unbind failed")

    with pytest.raises(LdapQueryError, match="LDAP 用户查询失败"):
        LdapClient(connection_factory=lambda *_args: Connection()).search_users(_config(), "secret")


def test_ldaps_connection_requires_certificate_and_applies_timeouts(monkeypatch):
    import app.services.ldap_client as module

    calls = {}
    monkeypatch.setattr(module, "Tls", lambda **kwargs: calls.setdefault("tls", kwargs) or "tls")
    monkeypatch.setattr(module, "Server", lambda *args, **kwargs: calls.setdefault("server", (args, kwargs)) or "server")
    monkeypatch.setattr(module, "Connection", lambda *args, **kwargs: calls.setdefault("connection", (args, kwargs)) or "connection")

    module.LdapClient._create_connection(_config(), "secret")

    assert calls["tls"]["validate"] == module.ssl.CERT_REQUIRED
    assert calls["server"][1]["connect_timeout"] == 5
    assert calls["connection"][1]["receive_timeout"] == 5
    assert calls["connection"][1]["auto_bind"] is True


def test_plain_ldap_opens_starttls_then_binds(monkeypatch):
    import app.services.ldap_client as module

    calls = []

    class Connection:
        def __init__(self, *_args, **kwargs):
            calls.append(("connection", kwargs))

        def open(self):
            calls.append(("open", {}))
            return True

        def start_tls(self):
            calls.append(("start_tls", {}))
            return True

        def bind(self):
            calls.append(("bind", {}))
            return True

    monkeypatch.setattr(module, "Tls", lambda **kwargs: calls.append(("tls", kwargs)) or "tls")
    monkeypatch.setattr(module, "Server", lambda *_args, **_kwargs: "server")
    monkeypatch.setattr(module, "Connection", Connection)
    config = _config()
    config.protocol = "ldap"

    module.LdapClient._create_connection(config, "secret")

    assert [name for name, _ in calls] == ["tls", "connection", "open", "start_tls", "bind"]
    assert calls[0][1]["validate"] == module.ssl.CERT_REQUIRED
    assert calls[1][1]["auto_bind"] is False


def test_starttls_failure_maps_to_stable_tls_error(monkeypatch):
    import app.services.ldap_client as module

    class Connection:
        def __init__(self, *_args, **_kwargs): pass
        def open(self): return True
        def start_tls(self): raise LDAPStartTLSError("certificate secret detail")

    monkeypatch.setattr(module, "Tls", lambda **_kwargs: "tls")
    monkeypatch.setattr(module, "Server", lambda *_args, **_kwargs: "server")
    monkeypatch.setattr(module, "Connection", Connection)
    config = _config()
    config.protocol = "ldap"

    with pytest.raises(module.LdapTlsError, match="^LDAP TLS 安全连接失败$"):
        module.LdapClient().search_users(config, "secret")


def test_bind_failure_maps_to_stable_connection_error():
    from app.services.ldap_client import LdapBindError, LdapClient

    def fail_bind(*_args):
        raise LDAPBindError("invalidCredentials and secret detail")

    with pytest.raises(LdapBindError, match="^LDAP 绑定认证失败$"):
        LdapClient(connection_factory=fail_bind).search_users(_config(), "secret")


def test_query_permission_failure_maps_to_stable_query_error():
    from app.services.ldap_client import LdapClient, LdapPermissionError

    connection = SimpleNamespace(entries=[], result={})
    connection.search = lambda **_kwargs: (_ for _ in ()).throw(LDAPInsufficientAccessRightsResult())
    with pytest.raises(LdapPermissionError, match="^LDAP 绑定账号没有用户目录查询权限$"):
        LdapClient(connection_factory=lambda *_args: connection).search_users(_config(), "secret")


def test_invalid_filter_exception_maps_to_stable_query_error():
    from app.services.ldap_client import LdapClient, LdapQueryError

    connection = SimpleNamespace(entries=[], result={})
    connection.search = lambda **_kwargs: (_ for _ in ()).throw(LDAPInvalidFilterError("detail"))
    with pytest.raises(LdapQueryError, match="^LDAP 用户筛选器格式不正确$"):
        LdapClient(connection_factory=lambda *_args: connection).search_users(_config(), "secret")


def test_network_exception_maps_to_stable_network_error():
    from app.services.ldap_client import LdapClient, LdapNetworkError

    def fail(*_args):
        raise LDAPSocketOpenError("server and secret detail")

    with pytest.raises(LdapNetworkError, match="^LDAP 服务器不可达$"):
        LdapClient(connection_factory=fail).search_users(_config(), "secret")


def test_cursor_is_decoded_and_only_one_paged_search_is_executed():
    from app.services.ldap_client import LdapClient

    calls = []
    connection = SimpleNamespace(entries=[], result={})
    connection.search = lambda **kwargs: calls.append(kwargs) or True

    LdapClient(connection_factory=lambda *_args: connection).search_users(
        _config(), "secret", cursor="cHJldmlvdXM", page_size=20
    )

    assert len(calls) == 1
    assert calls[0]["paged_cookie"] == b"previous"


def test_invalid_cursor_is_rejected_before_connecting():
    from app.services.ldap_client import LdapClient, LdapQueryError

    with pytest.raises(LdapQueryError, match="^分页游标无效$"):
        LdapClient(connection_factory=lambda *_args: pytest.fail("must not connect")).search_users(
            _config(), "secret", cursor="not+base64!"
        )


def test_exact_object_guid_lookup_uses_binary_little_endian_filter():
    from app.services.ldap_client import LdapClient

    calls = []
    connection = SimpleNamespace(entries=[], result={})
    connection.search = lambda **kwargs: calls.append(kwargs) or True

    result = LdapClient(connection_factory=lambda *_args: connection).search_user_by_external_id(
        _config(), "secret", "00112233-4455-6677-8899-aabbccddeeff"
    )

    assert result is None
    assert calls == [{
        "search_base": "OU=Employees,DC=example,DC=com",
        "search_filter": "(&(&(objectCategory=person)(objectClass=user))(objectGUID=\\33\\22\\11\\00\\55\\44\\77\\66\\88\\99\\aa\\bb\\cc\\dd\\ee\\ff))",
        "attributes": LdapClient._attributes(_config()),
        "size_limit": 2,
    }]


def _config():
    return SimpleNamespace(
        protocol="ldaps",
        host="dc.example.com",
        port=636,
        connect_timeout=5,
        page_size=50,
        base_dn="DC=example,DC=com",
        bind_username="svc@example.com",
        user_base_dn="OU=Employees,DC=example,DC=com",
        user_filter="(&(objectCategory=person)(objectClass=user))",
        exclude_disabled=True,
        username_attribute="sAMAccountName",
        employee_no_attribute="employeeID",
        full_name_attribute="displayName",
        email_attribute="mail",
        mobile_attribute="mobile",
        department_attribute="department",
        external_id_attribute="objectGUID",
    )

import base64
import binascii
import ssl
import uuid
from dataclasses import dataclass
from typing import Callable

from ldap3 import NONE, Connection, Server, Tls
from ldap3.core.exceptions import (
    LDAPBindError as Ldap3BindError,
    LDAPCertificateError,
    LDAPCommunicationError,
    LDAPException,
    LDAPInsufficientAccessRightsResult,
    LDAPInvalidCredentialsResult,
    LDAPInvalidFilterError,
    LDAPSocketOpenError,
    LDAPSSLConfigurationError,
    LDAPStartTLSError,
)
from ldap3.utils.conv import escape_bytes, escape_filter_chars


PAGED_RESULTS_OID = "1.2.840.113556.1.4.319"


@dataclass
class LdapSearchResult:
    items: list[dict]
    next_cursor: str | None
    total: int | None = None


class LdapClient:
    def __init__(self, connection_factory: Callable | None = None):
        self._connection_factory = connection_factory or self._create_connection

    def test_connection(self, config, password: str) -> int:
        return len(self.search_users(config, password, page_size=1).items)

    def search_users(
        self,
        config,
        password: str,
        query: str | None = None,
        cursor: str | None = None,
        page_size: int | None = None,
        user_base_dn: str | None = None,
        exclude_disabled: bool | None = None,
    ) -> LdapSearchResult:
        if query and any(char in query for char in "()*\\\x00"):
            raise LdapQueryError("搜索关键字包含非法字符")
        cookie = self._decode_cursor(cursor)
        connection = None
        try:
            connection = self._connection_factory(config, password)
            search_base = (
                config.user_base_dn or config.base_dn
                if user_base_dn is None
                else user_base_dn.strip() or config.base_dn
            )
            ok = connection.search(
                search_base=search_base,
                search_filter=self._search_filter(config, query, exclude_disabled),
                attributes=self._attributes(config),
                paged_size=page_size or config.page_size,
                paged_cookie=cookie,
            )
            if ok is False:
                if connection.result.get("description") == "insufficientAccessRights":
                    raise LdapPermissionError("LDAP 绑定账号没有用户目录查询权限")
                raise LdapQueryError("LDAP 用户查询失败")
            return LdapSearchResult(
                items=[self._map_entry(entry, config) for entry in connection.entries],
                next_cursor=self._encode_cursor(self._cookie(connection.result)),
                total=self._total(connection.result),
            )
        except (LdapQueryError, LdapPermissionError, LdapNetworkError, LdapTlsError, LdapBindError):
            raise
        except LDAPInvalidFilterError as error:
            raise LdapQueryError("LDAP 用户筛选器格式不正确") from error
        except LDAPInsufficientAccessRightsResult as error:
            raise LdapPermissionError("LDAP 绑定账号没有用户目录查询权限") from error
        except (LDAPCertificateError, LDAPSSLConfigurationError, LDAPStartTLSError) as error:
            raise LdapTlsError("LDAP TLS 安全连接失败") from error
        except (Ldap3BindError, LDAPInvalidCredentialsResult) as error:
            raise LdapBindError("LDAP 绑定认证失败") from error
        except (LDAPSocketOpenError, LDAPCommunicationError, OSError) as error:
            raise LdapNetworkError("LDAP 服务器不可达") from error
        except (LDAPException, ValueError) as error:
            raise LdapConnectionError("无法连接或查询 LDAP 目录") from error
        finally:
            if connection is not None and callable(getattr(connection, "unbind", None)):
                try:
                    connection.unbind()
                except Exception:
                    pass

    def search_user_by_external_id(self, config, password: str, external_id: str) -> dict | None:
        connection = None
        try:
            connection = self._connection_factory(config, password)
            external_filter = self._external_id_filter(config.external_id_attribute, external_id)
            ok = connection.search(
                search_base=config.user_base_dn or config.base_dn,
                search_filter=f"(&{config.user_filter}{external_filter})",
                attributes=self._attributes(config),
                size_limit=2,
            )
            if ok is False:
                if connection.result.get("description") == "insufficientAccessRights":
                    raise LdapPermissionError("LDAP 绑定账号没有用户目录查询权限")
                raise LdapQueryError("LDAP 用户查询失败")
            items = [self._map_entry(entry, config) for entry in connection.entries]
            if len(items) > 1:
                raise LdapQueryError("LDAP 唯一标识匹配到多个目录用户")
            return items[0] if items else None
        except (LdapQueryError, LdapPermissionError, LdapNetworkError, LdapTlsError, LdapBindError):
            raise
        except LDAPInvalidFilterError as error:
            raise LdapQueryError("LDAP 用户筛选器格式不正确") from error
        except LDAPInsufficientAccessRightsResult as error:
            raise LdapPermissionError("LDAP 绑定账号没有用户目录查询权限") from error
        except (LDAPCertificateError, LDAPSSLConfigurationError, LDAPStartTLSError) as error:
            raise LdapTlsError("LDAP TLS 安全连接失败") from error
        except (Ldap3BindError, LDAPInvalidCredentialsResult) as error:
            raise LdapBindError("LDAP 绑定认证失败") from error
        except (LDAPSocketOpenError, LDAPCommunicationError, OSError) as error:
            raise LdapNetworkError("LDAP 服务器不可达") from error
        except (LDAPException, ValueError) as error:
            raise LdapConnectionError("无法连接或查询 LDAP 目录") from error
        finally:
            if connection is not None and callable(getattr(connection, "unbind", None)):
                try:
                    connection.unbind()
                except Exception:
                    pass

    @staticmethod
    def _external_id_filter(attribute: str, external_id: str) -> str:
        if attribute.casefold() == "objectguid":
            try:
                value = escape_bytes(uuid.UUID(external_id).bytes_le)
            except ValueError as error:
                raise LdapQueryError("LDAP 唯一标识格式不正确") from error
        else:
            value = escape_filter_chars(external_id)
        return f"({attribute}={value})"

    @staticmethod
    def _create_connection(config, password: str):
        tls = Tls(validate=ssl.CERT_REQUIRED)
        server = Server(
            config.host,
            port=config.port,
            use_ssl=config.protocol == "ldaps",
            tls=tls,
            connect_timeout=config.connect_timeout,
            get_info=NONE,
        )
        connection = Connection(
            server,
            user=config.bind_username,
            password=password,
            auto_bind=config.protocol == "ldaps",
            receive_timeout=config.connect_timeout,
            raise_exceptions=True,
        )
        if config.protocol == "ldap":
            if connection.open() is False:
                raise LdapNetworkError("LDAP 服务器不可达")
            if connection.start_tls() is False:
                raise LdapTlsError("LDAP TLS 安全连接失败")
            if connection.bind() is False:
                raise LdapBindError("LDAP 绑定认证失败")
        return connection

    @staticmethod
    def _attributes(config) -> list[str]:
        return list(dict.fromkeys([
            config.username_attribute, config.employee_no_attribute, config.full_name_attribute,
            config.email_attribute, config.mobile_attribute, config.department_attribute,
            config.external_id_attribute, "userAccountControl", "distinguishedName",
        ]))

    @staticmethod
    def _search_filter(config, query: str | None, exclude_disabled: bool | None = None) -> str:
        clauses = [config.user_filter]
        if config.exclude_disabled if exclude_disabled is None else exclude_disabled:
            clauses.append("(!(userAccountControl:1.2.840.113556.1.4.803:=2))")
        if query:
            value = escape_filter_chars(query.strip())
            clauses.append(
                "(|" + "".join(
                    f"({attribute}=*{value}*)" for attribute in (
                        config.username_attribute, config.employee_no_attribute,
                        config.full_name_attribute, config.email_attribute,
                    )
                ) + ")"
            )
        return f"(&{''.join(clauses)})"

    @classmethod
    def _map_entry(cls, entry, config) -> dict:
        values = entry.entry_attributes_as_dict
        uac = cls._one(values.get("userAccountControl"))
        return {
            "username": cls._text(values.get(config.username_attribute)),
            "employee_no": cls._text(values.get(config.employee_no_attribute)),
            "full_name": cls._text(values.get(config.full_name_attribute)),
            "email": cls._text(values.get(config.email_attribute)),
            "mobile": cls._text(values.get(config.mobile_attribute)),
            "department": cls._text(values.get(config.department_attribute)),
            "external_id": cls._external_id(cls._one(values.get(config.external_id_attribute))),
            "dn": getattr(entry, "entry_dn", None) or cls._text(values.get("distinguishedName")),
            "enabled": not (isinstance(uac, int) and bool(uac & 2)),
        }

    @staticmethod
    def _one(value):
        if isinstance(value, (list, tuple)):
            return value[0] if value else None
        return value

    @classmethod
    def _text(cls, value) -> str | None:
        value = cls._one(value)
        return None if value is None else str(value)

    @staticmethod
    def _external_id(value) -> str | None:
        if value is None:
            return None
        if isinstance(value, bytes) and len(value) == 16:
            return str(uuid.UUID(bytes_le=value))
        return str(value)

    @staticmethod
    def _cookie(result: dict) -> bytes | None:
        return result.get("controls", {}).get(PAGED_RESULTS_OID, {}).get("value", {}).get("cookie") or None

    @staticmethod
    def _total(result: dict) -> int | None:
        value = result.get("controls", {}).get(PAGED_RESULTS_OID, {}).get("value", {}).get("size")
        try:
            total = int(value)
        except (TypeError, ValueError):
            return None
        return total if total >= 0 else None

    @staticmethod
    def _encode_cursor(cookie: bytes | None) -> str | None:
        return base64.urlsafe_b64encode(cookie).decode("ascii").rstrip("=") if cookie else None

    @staticmethod
    def _decode_cursor(cursor: str | None) -> bytes | None:
        if not cursor:
            return None
        if not all(char.isalnum() or char in "-_" for char in cursor):
            raise LdapQueryError("分页游标无效")
        try:
            return base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        except (binascii.Error, ValueError):
            raise LdapQueryError("分页游标无效") from None


class LdapConnectionError(Exception):
    pass


class LdapQueryError(Exception):
    pass


class LdapPermissionError(LdapConnectionError):
    pass


class LdapNetworkError(LdapConnectionError):
    pass


class LdapTlsError(LdapConnectionError):
    pass


class LdapBindError(LdapConnectionError):
    pass


ldap_client = LdapClient()

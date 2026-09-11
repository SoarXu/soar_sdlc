import ssl
from typing import Callable

from fastapi import HTTPException
from ldap3 import NONE, Connection, Server, Tls
from ldap3.core.exceptions import (
    LDAPBindError,
    LDAPCertificateError,
    LDAPCommunicationError,
    LDAPException,
    LDAPInvalidCredentialsResult,
    LDAPSocketOpenError,
    LDAPSSLConfigurationError,
    LDAPStartTLSError,
)
from sqlalchemy.orm import Session

from app.services.ldap_config_service import require_ready_config


class LdapCredentialsRejected(Exception):
    pass


class LdapDirectoryUnavailable(Exception):
    pass


class LdapUserAuthenticator:
    def __init__(self, connection_factory: Callable | None = None):
        self._connection_factory = connection_factory or self._create_connection

    def authenticate(self, config, user_dn: str, password: str) -> None:
        if not password:
            raise LdapCredentialsRejected()
        connection = None
        try:
            connection = self._connection_factory(config, user_dn, password)
        except (LDAPBindError, LDAPInvalidCredentialsResult) as error:
            raise LdapCredentialsRejected() from error
        except (LDAPCertificateError, LDAPSSLConfigurationError, LDAPStartTLSError) as error:
            raise LdapDirectoryUnavailable() from error
        except (LDAPSocketOpenError, LDAPCommunicationError, LDAPException, OSError, ValueError) as error:
            raise LdapDirectoryUnavailable() from error
        finally:
            if connection is not None and callable(getattr(connection, "unbind", None)):
                try:
                    connection.unbind()
                except Exception:
                    pass

    @staticmethod
    def _create_connection(config, user_dn: str, password: str):
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
            user=user_dn,
            password=password,
            auto_bind=config.protocol == "ldaps",
            receive_timeout=config.connect_timeout,
            raise_exceptions=True,
        )
        if config.protocol == "ldap":
            if connection.open() is False:
                raise LdapDirectoryUnavailable()
            if connection.start_tls() is False:
                raise LdapDirectoryUnavailable()
            if connection.bind() is False:
                raise LdapCredentialsRejected()
        return connection


ldap_user_authenticator = LdapUserAuthenticator()


def authenticate_ldap_user(
    db: Session,
    user,
    password: str,
    authenticator: LdapUserAuthenticator | None = None,
) -> bool:
    if not user.ldap_external_id or not user.ldap_dn:
        return False
    try:
        config = require_ready_config(db)
    except HTTPException as error:
        raise LdapDirectoryUnavailable() from error
    try:
        (authenticator or ldap_user_authenticator).authenticate(config, user.ldap_dn, password)
    except LdapCredentialsRejected:
        return False
    return True

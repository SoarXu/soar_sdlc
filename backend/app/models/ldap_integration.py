from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LdapIntegrationConfig(Base):
    __tablename__ = "ldap_integration_config"
    __table_args__ = (CheckConstraint("id = 1", name="ck_ldap_integration_config_singleton"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    protocol: Mapped[str] = mapped_column(String(8), default="ldaps")
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=636)
    connect_timeout: Mapped[int] = mapped_column(Integer, default=5)
    base_dn: Mapped[str] = mapped_column(String(512))
    bind_username: Mapped[str] = mapped_column(String(512))
    bind_password_encrypted: Mapped[str] = mapped_column(Text)
    user_base_dn: Mapped[str | None] = mapped_column(String(512), nullable=True)
    user_filter: Mapped[str] = mapped_column(String(1000), default="(&(objectCategory=person)(objectClass=user))")
    exclude_disabled: Mapped[bool] = mapped_column(Boolean, default=True)
    page_size: Mapped[int] = mapped_column(Integer, default=50)
    username_attribute: Mapped[str] = mapped_column(String(64), default="sAMAccountName")
    employee_no_attribute: Mapped[str] = mapped_column(String(64), default="employeeID")
    full_name_attribute: Mapped[str] = mapped_column(String(64), default="displayName")
    email_attribute: Mapped[str] = mapped_column(String(64), default="mail")
    mobile_attribute: Mapped[str] = mapped_column(String(64), default="mobile")
    department_attribute: Mapped[str] = mapped_column(String(64), default="department")
    external_id_attribute: Mapped[str] = mapped_column(String(64), default="objectGUID")
    tested_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), server_onupdate=text("CURRENT_TIMESTAMP")
    )

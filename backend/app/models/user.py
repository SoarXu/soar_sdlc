from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Computed, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employee_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active_employee_no: Mapped[str | None] = mapped_column(
        String(64),
        Computed(
            "CASE WHEN deleted = 0 AND is_active = 1 AND employee_no IS NOT NULL "
            "AND TRIM(employee_no) <> '' THEN employee_no ELSE NULL END",
            persisted=True,
        ),
        nullable=True,
        unique=True,
    )
    auth_source: Mapped[str] = mapped_column(String(16), default="local", server_default=text("'local'"))
    ldap_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    ldap_dn: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ldap_last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
    deleted: Mapped[int] = mapped_column(Integer, default=0)
    delete_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

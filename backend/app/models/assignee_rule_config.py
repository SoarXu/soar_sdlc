from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AssigneeRuleConfig(Base):
    __tablename__ = "assignee_rule_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_owner_roles: Mapped[str] = mapped_column(String(255), default="")
    task_owner_roles: Mapped[str] = mapped_column(String(255), default="")
    test_case_tester_roles: Mapped[str] = mapped_column(String(255), default="")
    test_run_owner_roles: Mapped[str] = mapped_column(String(255), default="")
    bug_owner_roles: Mapped[str] = mapped_column(String(255), default="")
    lifecycle_status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

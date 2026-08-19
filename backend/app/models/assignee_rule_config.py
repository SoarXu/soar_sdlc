from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AssigneeRuleConfig(Base):
    __tablename__ = "assignee_rule_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_owner_role_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    task_owner_role_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    test_case_tester_role_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    test_run_owner_role_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    bug_owner_role_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    lifecycle_status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

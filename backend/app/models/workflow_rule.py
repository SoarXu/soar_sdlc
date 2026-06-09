from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class WorkflowRule(Base):
    __tablename__ = "workflow_rules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    rule_name: Mapped[str] = mapped_column(String(150))
    scope_type: Mapped[str] = mapped_column(String(32))
    scope_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    target_object: Mapped[str] = mapped_column(String(64))
    trigger_action: Mapped[str] = mapped_column(String(64))
    condition_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    action_json: Mapped[dict | list] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    block_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    creator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updater_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

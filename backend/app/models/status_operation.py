from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StatusOperationLog(Base):
    __tablename__ = "status_operation_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    object_type: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(32))
    operation_kind: Mapped[str] = mapped_column(String(16), default="state", server_default=text("'state'"))
    workflow_definition_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("workflow_definitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    from_state_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("workflow_states.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    to_state_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("workflow_states.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    from_state_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    to_state_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_time: Mapped[datetime] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_delegated: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    delegated_owner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    delegated_owner_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delegate_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selected_values: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    default_target_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_target_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    next_owner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    next_owner_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    blocker_messages: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

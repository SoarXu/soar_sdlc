from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    object_type: Mapped[str] = mapped_column(String(32), index=True)
    scope_type: Mapped[str] = mapped_column(String(32), default="system")
    scope_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    template_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    parent_definition_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    initial_state_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("workflow_states.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    is_default_template: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )


class WorkflowState(Base):
    __tablename__ = "workflow_states"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    definition_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        index=True,
    )
    status_name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(32), default="normal")
    color: Mapped[str] = mapped_column(String(32), default="#2563eb")
    x: Mapped[int] = mapped_column(Integer, default=0)
    y: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )


class WorkflowTransition(Base):
    __tablename__ = "workflow_transitions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    definition_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        index=True,
    )
    action_key: Mapped[str] = mapped_column(String(64))
    action_name: Mapped[str] = mapped_column(String(100))
    from_state_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("workflow_states.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    to_state_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("workflow_states.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    allowed_roles: Mapped[str] = mapped_column(String(255), default="")
    handler_rule: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trigger_config: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    condition_config: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    validator_config: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    post_action_config: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    ui_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    form_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

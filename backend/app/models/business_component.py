from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.types import UnsignedBigInteger


class BusinessComponent(Base):
    __tablename__ = "business_components"
    __table_args__ = (
        UniqueConstraint("project_id", "source_project_id", name="uk_business_component_project_source"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    source_project_name_snapshot: Mapped[str | None] = mapped_column(String(150), nullable=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    workflow_scheme_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("assignee_rule_configs.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"), nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), server_onupdate=text("CURRENT_TIMESTAMP")
    )
    members: Mapped[list["BusinessComponentMember"]] = relationship(
        back_populates="component", lazy="selectin", cascade="all, delete-orphan"
    )


class BusinessComponentMember(Base):
    __tablename__ = "business_component_members"
    __table_args__ = (
        UniqueConstraint("component_id", "user_id", name="uk_business_component_member"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    component_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("business_components.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"), nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), server_onupdate=text("CURRENT_TIMESTAMP")
    )
    component: Mapped[BusinessComponent] = relationship(back_populates="members")


class BusinessComponentTransitionRoute(Base):
    __tablename__ = "business_component_transition_routes"
    __table_args__ = (
        UniqueConstraint("component_id", "object_type", "transition_id", name="uk_component_transition_route"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    component_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("business_components.id", ondelete="CASCADE"), nullable=False, index=True
    )
    object_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    transition_id: Mapped[int] = mapped_column(
        UnsignedBigInteger,
        ForeignKey("workflow_transitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    eligible_member_mode: Mapped[str] = mapped_column(String(32), default="component_role", nullable=False)
    eligible_role_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    eligible_user_ids: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    next_owner_mode: Mapped[str] = mapped_column(String(32), default="component_role", nullable=False)
    next_owner_role_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    next_owner_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fallback_mode: Mapped[str] = mapped_column(String(32), default="pending_assignment", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"), nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), server_onupdate=text("CURRENT_TIMESTAMP")
    )


class WorkItemComponent(Base):
    __tablename__ = "work_item_components"
    __table_args__ = (
        UniqueConstraint("object_type", "object_id", "component_id", name="uk_work_item_component"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    object_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    component_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("business_components.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    component_name_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class WorkflowMigrationLog(Base):
    __tablename__ = "workflow_migration_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    object_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    old_definition_id: Mapped[int] = mapped_column(
        UnsignedBigInteger,
        ForeignKey("workflow_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    old_state_id: Mapped[int] = mapped_column(
        UnsignedBigInteger,
        ForeignKey("workflow_states.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    new_definition_id: Mapped[int] = mapped_column(
        UnsignedBigInteger,
        ForeignKey("workflow_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    new_state_id: Mapped[int] = mapped_column(
        UnsignedBigInteger,
        ForeignKey("workflow_states.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

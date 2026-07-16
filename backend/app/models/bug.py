from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Bug(Base):
    __tablename__ = "bugs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    project_id: Mapped[int] = mapped_column(BigInteger)
    iteration_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    requirement_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    test_case_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    test_run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    bug_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str] = mapped_column(String(32), default="3")
    priority: Mapped[str] = mapped_column(String(32), default="3")
    owner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reporter_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    workflow_definition_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("workflow_definitions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    current_state_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("workflow_states.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    reproduce_steps: Mapped[str | None] = mapped_column(Text().with_variant(MEDIUMTEXT, "mysql"), nullable=True)
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending_handling")
    lifecycle_phase: Mapped[str] = mapped_column(String(32), default="development")
    resolution: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolve_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    verify_result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verify_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    close_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    creator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updater_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
    deleted: Mapped[int] = mapped_column(Integer, default=0)
    delete_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    current_state: Mapped["WorkflowState | None"] = relationship(foreign_keys=[current_state_id], lazy="joined")

    @property
    def status_name(self) -> str | None:
        return self.current_state.status_name if self.current_state else None


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tag_name: Mapped[str] = mapped_column(String(64))
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    object_type: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )


class ObjectTag(Base):
    __tablename__ = "object_tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    object_type: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[int] = mapped_column(BigInteger)
    tag_id: Mapped[int] = mapped_column(BigInteger)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    object_type: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[int] = mapped_column(BigInteger)
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uploader_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    upload_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

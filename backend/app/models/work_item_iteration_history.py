from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class WorkItemIterationHistory(Base):
    __tablename__ = "work_item_iteration_history"
    __table_args__ = (
        Index("idx_wiih_object", "object_type", "object_id", "left_at"),
        Index("idx_wiih_iteration", "iteration_id", "left_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    object_type: Mapped[str] = mapped_column(String(32), index=True)
    object_id: Mapped[int] = mapped_column(BigInteger, index=True)
    iteration_id: Mapped[int] = mapped_column(BigInteger, index=True)
    entered_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    entered_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    enter_reason: Mapped[str] = mapped_column(String(64))
    left_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    left_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    leave_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state_id_snapshot: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status_name_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    owner_id_snapshot: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    operation_log_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    migrated: Mapped[int] = mapped_column(Integer, default=0)

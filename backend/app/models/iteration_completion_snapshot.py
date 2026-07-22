from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class IterationCompletionSnapshot(Base):
    __tablename__ = "iteration_completion_snapshots"
    __table_args__ = (UniqueConstraint("iteration_id", name="uk_iteration_completion_snapshot_iteration"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    iteration_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("iterations.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    operation_log_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    iteration_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    counts: Mapped[dict] = mapped_column(JSON, nullable=False)
    terminal_counts: Mapped[dict] = mapped_column(JSON, nullable=False)
    items: Mapped[dict] = mapped_column(JSON, nullable=False)
    gate_result: Mapped[dict] = mapped_column(JSON, nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

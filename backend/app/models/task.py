from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, DECIMAL, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    project_id: Mapped[int] = mapped_column(BigInteger)
    source_project_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    iteration_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    requirement_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    task_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[str] = mapped_column(String(32), default="medium")
    owner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    estimated_hours: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    actual_hours: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="todo")
    lifecycle_phase: Mapped[str] = mapped_column(String(32), default="development")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_requirement_review_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
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

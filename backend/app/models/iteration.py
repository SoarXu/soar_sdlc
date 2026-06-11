from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Iteration(Base):
    __tablename__ = "iterations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    owner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="planning")
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class IterationProject(Base):
    __tablename__ = "iteration_projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    iteration_id: Mapped[int] = mapped_column(BigInteger)
    project_id: Mapped[int] = mapped_column(BigInteger)

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    project_id: Mapped[int] = mapped_column(BigInteger)
    iteration_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str] = mapped_column(String(150))
    test_owner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="planning")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class TestRunCase(Base):
    __tablename__ = "test_run_cases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    test_run_id: Mapped[int] = mapped_column(BigInteger)
    test_case_id: Mapped[int] = mapped_column(BigInteger)
    tester_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    result: Mapped[str] = mapped_column(String(32), default="not_run")
    execute_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TestCaseExecutionLog(Base):
    __tablename__ = "test_case_execution_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    test_case_id: Mapped[int] = mapped_column(BigInteger)
    executor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    execute_time: Mapped[datetime] = mapped_column(DateTime)
    result: Mapped[str] = mapped_column(String(32))
    steps_result_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

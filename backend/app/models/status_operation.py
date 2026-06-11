from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StatusOperationLog(Base):
    __tablename__ = "status_operation_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    object_type: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(32))
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_time: Mapped[datetime] = mapped_column(DateTime)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

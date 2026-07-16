from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class BugType(Base):
    __tablename__ = "bug_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    is_real_bug: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    default_target_status: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    sort_order: Mapped[int] = mapped_column(Integer, default=100, server_default=text("100"))
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

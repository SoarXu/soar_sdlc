from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class HandlerTransitionRule(Base):
    __tablename__ = "handler_transition_rules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    config_id: Mapped[int] = mapped_column(BigInteger, index=True)
    rule_type: Mapped[str] = mapped_column(String(32), default="advanced", index=True)
    object_type: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_type: Mapped[str] = mapped_column(String(64), default="keep_current")
    target_roles: Mapped[str] = mapped_column(String(255), default="")
    fallback_type: Mapped[str] = mapped_column(String(64), default="keep_current")
    fallback_roles: Mapped[str] = mapped_column(String(255), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class WorkflowComponent(Base):
    __tablename__ = "workflow_component_registry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    component_key: Mapped[str] = mapped_column(String(100), unique=True)
    component_type: Mapped[str] = mapped_column(String(32))
    component_name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    handler_key: Mapped[str] = mapped_column(String(100))
    config_schema: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

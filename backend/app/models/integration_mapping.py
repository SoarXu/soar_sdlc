from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ExternalIntegrationMapping(Base):
    __tablename__ = "external_integration_mapping"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    object_type: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[int] = mapped_column(BigInteger)
    external_project_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_object_type: Mapped[str] = mapped_column(String(64))
    external_object_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_iid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(32), default="pending")
    last_sync_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

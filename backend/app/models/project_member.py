from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ProjectMember(Base):
    __tablename__ = "project_members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    project_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    project_role: Mapped[str] = mapped_column(String(64))
    is_default_assignee: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    is_workbench_participant: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    join_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

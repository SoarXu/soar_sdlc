from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
    deleted: Mapped[int] = mapped_column(Integer, default=0)
    delete_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

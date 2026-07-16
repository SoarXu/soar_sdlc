from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BugTypeBase(BaseModel):
    type_key: str
    display_name: str
    is_real_bug: bool | None = None
    default_target_status: str
    enabled: bool = True
    sort_order: int = 100


class BugTypeCreate(BugTypeBase):
    pass


class BugTypeUpdate(BaseModel):
    display_name: str | None = None
    is_real_bug: bool | None = None
    default_target_status: str | None = None
    enabled: bool | None = None
    sort_order: int | None = None


class BugTypeRead(BugTypeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    create_time: datetime | None = None
    update_time: datetime | None = None

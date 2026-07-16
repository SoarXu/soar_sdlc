from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExceptionRuleBase(BaseModel):
    exception_key: str
    label: str
    object_type: str = "*"
    project_id: int | None = None
    priority: str | None = None
    status: str | None = None
    threshold_hours: int | None = None
    threshold_count: int | None = None
    enabled: bool = True
    sort_order: int = 100


class ExceptionRuleCreate(ExceptionRuleBase):
    pass


class ExceptionRuleUpdate(BaseModel):
    label: str | None = None
    object_type: str | None = None
    project_id: int | None = None
    priority: str | None = None
    status: str | None = None
    threshold_hours: int | None = None
    threshold_count: int | None = None
    enabled: bool | None = None
    sort_order: int | None = None


class ExceptionRuleRead(ExceptionRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creator_id: int | None = None
    updater_id: int | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None

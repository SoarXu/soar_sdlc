from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StatusOperationCreate(BaseModel):
    effective_time: datetime | None = None
    remark: str | None = None


class StatusOperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_type: str
    object_id: int
    action: str
    from_status: str | None = None
    to_status: str
    effective_time: datetime
    remark: str | None = None
    actor_id: int | None = None
    actor_name: str | None = None
    create_time: datetime | None = None

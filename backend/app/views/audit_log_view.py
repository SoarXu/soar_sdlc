from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None = None
    action: str
    object_type: str
    object_id: int | None = None
    before_data: dict | list | None = None
    after_data: dict | list | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    create_time: datetime | None = None

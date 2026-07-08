from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receiver_id: int
    title: str
    content: str | None = None
    object_type: str | None = None
    object_id: int | None = None
    category: str
    source_type: str | None = None
    source_id: int | None = None
    metadata_json: dict | list | None = None
    is_read: bool
    read_time: datetime | None = None
    create_time: datetime | None = None

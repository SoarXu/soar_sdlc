from datetime import datetime

from pydantic import BaseModel


class ObjectWatchToggleRequest(BaseModel):
    object_type: str
    object_id: int


class ObjectWatcherRead(BaseModel):
    user_id: int
    full_name: str | None = None
    source: str | None = None
    enabled: bool = True
    update_time: datetime | None = None


class ObjectWatchRead(BaseModel):
    object_type: str
    object_id: int
    watched: bool
    watcher_count: int
    watchers: list[ObjectWatcherRead]

from datetime import datetime

from pydantic import BaseModel, Field


class WorkItemCommentCreate(BaseModel):
    object_type: str
    object_id: int
    body: str
    mentioned_user_ids: list[int] = Field(default_factory=list)


class WorkItemCommentRead(BaseModel):
    id: int
    object_type: str
    object_id: int
    author_id: int
    author_name: str | None = None
    body: str
    mentioned_user_ids: list[int] = Field(default_factory=list)
    mentions_metadata: list[dict] = Field(default_factory=list)
    create_time: datetime | None = None


class WorkItemCommentListRead(BaseModel):
    items: list[WorkItemCommentRead] = Field(default_factory=list)

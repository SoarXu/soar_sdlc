from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field


def _normalize_optional_text(value):
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


ProposerText = Annotated[
    str | None,
    BeforeValidator(_normalize_optional_text),
]


class WorkItemRead(BaseModel):
    id: int
    object_type: str
    title: str
    project_id: int | None = None
    project_name: str | None = None
    iteration_id: int | None = None
    iteration_name: str | None = None
    status: str
    status_name: str | None = None
    state_category: str | None = None
    priority: str | None = None
    severity: str | None = None
    owner_id: int | None = None
    create_time: datetime | None = None
    waiting_hours: float = 0
    overdue: bool = False


class WorkItemListRead(BaseModel):
    items: list[WorkItemRead] = Field(default_factory=list)
    total: int = 0
    overdue_count: int = 0

from datetime import datetime

from pydantic import BaseModel, Field


class WorkItemRef(BaseModel):
    object_type: str
    id: int


class WorkItemRead(BaseModel):
    id: int
    object_type: str
    title: str
    project_id: int | None = None
    project_name: str | None = None
    iteration_id: int | None = None
    iteration_name: str | None = None
    status: str
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


class WorkItemAssignRequest(BaseModel):
    owner_id: int
    remark: str | None = None


class WorkItemClaimRequest(BaseModel):
    remark: str | None = None


class WorkItemBatchAssignRequest(BaseModel):
    items: list[WorkItemRef]
    owner_id: int
    remark: str | None = None


class WorkItemAutoAssignRequest(BaseModel):
    items: list[WorkItemRef] | None = None


class WorkItemAssignResult(BaseModel):
    object_type: str
    id: int
    owner_id: int | None = None


class WorkItemFailure(BaseModel):
    object_type: str
    id: int
    reason: str


class WorkItemBatchResult(BaseModel):
    success_items: list[WorkItemAssignResult] = Field(default_factory=list)
    failures: list[WorkItemFailure] = Field(default_factory=list)

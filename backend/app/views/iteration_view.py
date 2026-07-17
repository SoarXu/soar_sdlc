from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


IterationStatus = Literal["planning", "active", "completed", "canceled"]


class IterationBase(BaseModel):
    project_id: int | None = None
    project_ids: list[int] = []
    name: str
    owner_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    status: IterationStatus = "planning"
    lifecycle_phase: str | None = None
    goal: str | None = None


class IterationCreate(IterationBase):
    pass


class IterationUpdate(BaseModel):
    project_id: int | None = None
    project_ids: list[int] | None = None
    name: str | None = None
    owner_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    status: IterationStatus | None = None
    lifecycle_phase: str | None = None
    goal: str | None = None
    updater_id: int | None = None


class IterationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_definition_id: int | None = None
    current_state_id: int | None = None
    status_name: str | None = None
    project_id: int | None = None
    project_ids: list[int] = []
    name: str
    owner_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    status: IterationStatus = "planning"
    lifecycle_phase: str | None = None
    goal: str | None = None
    creator_id: int | None = None
    updater_id: int | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None
    delete_time: datetime | None = None


class LinkRequirementsRequest(BaseModel):
    requirement_ids: list[int]


class LinkTasksRequest(BaseModel):
    task_ids: list[int]


class DeferIterationWorkItemsRequest(BaseModel):
    target_iteration_id: int
    requirement_ids: list[int] | None = None
    task_ids: list[int] | None = None
    remark: str | None = None


class DeferIterationWorkItemsResult(BaseModel):
    moved_requirement_ids: list[int]
    moved_task_ids: list[int]

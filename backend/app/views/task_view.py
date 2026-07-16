from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class TaskBase(BaseModel):
    project_id: int
    source_project_id: int | None = None
    iteration_id: int | None = None
    requirement_id: int | None = None
    title: str
    task_type: str | None = None
    priority: str = "medium"
    owner_id: int | None = None
    estimated_hours: Decimal | None = None
    actual_hours: Decimal | None = None
    due_date: date | None = None
    lifecycle_phase: str | None = None
    description: str | None = None
    source_requirement_review_status: str | None = None


class TaskCreate(TaskBase):
    model_config = ConfigDict(extra="forbid")

    task_type: Literal[
        "requirement_implementation",
        "bug_fix",
        "test_support",
        "standalone_operation",
    ] | None = None


class LinkedTaskCreate(BaseModel):
    source_type: Literal["requirement", "bug", "test_case", "test_run"]
    source_id: int
    title: str
    task_type: Literal[
        "requirement_implementation",
        "bug_fix",
        "test_support",
        "standalone_operation",
    ] | None = None
    priority: str = "medium"
    owner_id: int | None = None
    due_date: date | None = None
    description: str | None = None
    override_reason: str | None = None


class TaskSourceRead(BaseModel):
    source_type: str
    source_id: int
    relation_type: str = "linked_task"


class LinkedTaskSummary(BaseModel):
    id: int
    title: str
    task_type: str | None = None
    status_name: str
    owner_id: int | None = None


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int | None = None
    source_project_id: int | None = None
    iteration_id: int | None = None
    requirement_id: int | None = None
    title: str | None = None
    task_type: Literal[
        "requirement_implementation",
        "bug_fix",
        "test_support",
        "standalone_operation",
    ] | None = None
    priority: str | None = None
    owner_id: int | None = None
    estimated_hours: Decimal | None = None
    actual_hours: Decimal | None = None
    due_date: date | None = None
    lifecycle_phase: str | None = None
    description: str | None = None
    source_requirement_review_status: str | None = None
    updater_id: int | None = None


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_definition_id: int
    current_state_id: int
    status_name: str
    state_category: str
    creator_id: int | None = None
    updater_id: int | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None
    delete_time: datetime | None = None
    source_relations: list[TaskSourceRead] = Field(default_factory=list)

    @field_serializer("estimated_hours", "actual_hours")
    def serialize_decimal(self, value: Decimal | None):
        return float(value) if value is not None else None

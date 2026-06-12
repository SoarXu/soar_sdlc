from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer


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
    status: str = "todo"
    lifecycle_phase: str | None = None
    description: str | None = None
    source_requirement_review_status: str | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    project_id: int | None = None
    source_project_id: int | None = None
    iteration_id: int | None = None
    requirement_id: int | None = None
    title: str | None = None
    task_type: str | None = None
    priority: str | None = None
    owner_id: int | None = None
    estimated_hours: Decimal | None = None
    actual_hours: Decimal | None = None
    due_date: date | None = None
    status: str | None = None
    lifecycle_phase: str | None = None
    description: str | None = None
    source_requirement_review_status: str | None = None
    updater_id: int | None = None


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creator_id: int | None = None
    updater_id: int | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None
    delete_time: datetime | None = None

    @field_serializer("estimated_hours", "actual_hours")
    def serialize_decimal(self, value: Decimal | None):
        return float(value) if value is not None else None

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RequirementBase(BaseModel):
    project_id: int
    source_project_id: int | None = None
    iteration_id: int | None = None
    title: str
    requirement_type: str | None = None
    priority: str = "3"
    owner_id: int | None = None
    proposer_id: int | None = None
    status: str = "draft"
    review_status: str = "not_required"
    description: str | None = None
    acceptance_criteria: str | None = None
    source_reviewed: bool = False


class RequirementCreate(RequirementBase):
    pass


class RequirementUpdate(BaseModel):
    project_id: int | None = None
    source_project_id: int | None = None
    iteration_id: int | None = None
    title: str | None = None
    requirement_type: str | None = None
    priority: str | None = None
    owner_id: int | None = None
    proposer_id: int | None = None
    status: str | None = None
    review_status: str | None = None
    description: str | None = None
    acceptance_criteria: str | None = None
    source_reviewed: bool | None = None
    updater_id: int | None = None


class GenerateTaskRequest(BaseModel):
    title: str | None = None
    task_type: str | None = None
    priority: str | None = None
    due_date: str | None = None
    description: str | None = None


class RequirementRead(RequirementBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creator_id: int | None = None
    updater_id: int | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None
    delete_time: datetime | None = None

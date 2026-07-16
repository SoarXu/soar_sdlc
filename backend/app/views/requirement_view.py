from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.views.task_view import LinkedTaskSummary


class RequirementBase(BaseModel):
    project_id: int
    source_project_id: int | None = None
    iteration_id: int | None = None
    title: str
    requirement_type: str | None = None
    priority: str = "3"
    owner_id: int | None = None
    proposer_id: int | None = None
    lifecycle_phase: str | None = None
    review_status: str = "not_required"
    description: str | None = None
    acceptance_criteria: str | None = None
    source_reviewed: bool = False


class RequirementCreate(RequirementBase):
    model_config = ConfigDict(extra="forbid")


class RequirementUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: int | None = None
    source_project_id: int | None = None
    iteration_id: int | None = None
    title: str | None = None
    requirement_type: str | None = None
    priority: str | None = None
    owner_id: int | None = None
    proposer_id: int | None = None
    lifecycle_phase: str | None = None
    review_status: str | None = None
    description: str | None = None
    acceptance_criteria: str | None = None
    source_reviewed: bool | None = None
    updater_id: int | None = None


class RequirementRead(RequirementBase):
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
    linked_tasks: list[LinkedTaskSummary] = Field(default_factory=list)


class RequirementImportError(BaseModel):
    row_number: int
    messages: list[str]


class RequirementImportDuplicate(BaseModel):
    row_number: int
    project_id: int
    project_name: str
    title: str
    existing_requirement_id: int
    existing_requirement_title: str


class RequirementImportPreviewRead(BaseModel):
    valid_count: int
    error_count: int
    duplicate_count: int
    errors: list[RequirementImportError] = []
    duplicates: list[RequirementImportDuplicate] = []


class RequirementImportCommitRead(BaseModel):
    created_count: int
    updated_count: int
    error_count: int
    errors: list[RequirementImportError] = []

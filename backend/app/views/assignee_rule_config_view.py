from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AssigneeRuleConfigBase(BaseModel):
    name: str
    description: str | None = None
    requirement_owner_role_ids: list[int] = []
    task_owner_role_ids: list[int] = []
    test_case_tester_role_ids: list[int] = []
    test_run_owner_role_ids: list[int] = []
    bug_owner_role_ids: list[int] = []


class WorkflowTemplateSourceRef(BaseModel):
    source_type: Literal["system", "scheme"]
    source_id: str


class WorkflowTemplateSourceRead(WorkflowTemplateSourceRef):
    name: str
    description: str | None = None
    lifecycle_status: str | None = None


class AssigneeRuleConfigCreate(AssigneeRuleConfigBase):
    model_config = ConfigDict(extra="forbid")

    creation_mode: Literal["blank", "template"] = "blank"
    template_source: WorkflowTemplateSourceRef | None = None


class AssigneeRuleConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    requirement_owner_role_ids: list[int] | None = None
    task_owner_role_ids: list[int] | None = None
    test_case_tester_role_ids: list[int] | None = None
    test_run_owner_role_ids: list[int] | None = None
    bug_owner_role_ids: list[int] | None = None


class AssigneeRuleConfigRead(AssigneeRuleConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lifecycle_status: str
    create_time: datetime | None = None
    update_time: datetime | None = None

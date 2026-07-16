from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AssigneeRuleConfigBase(BaseModel):
    name: str
    description: str | None = None
    requirement_owner_roles: str = ""
    task_owner_roles: str = ""
    test_case_tester_roles: str = ""
    test_run_owner_roles: str = ""
    bug_owner_roles: str = ""


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
    requirement_owner_roles: str | None = None
    task_owner_roles: str | None = None
    test_case_tester_roles: str | None = None
    test_run_owner_roles: str | None = None
    bug_owner_roles: str | None = None


class AssigneeRuleConfigRead(AssigneeRuleConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lifecycle_status: str
    create_time: datetime | None = None
    update_time: datetime | None = None

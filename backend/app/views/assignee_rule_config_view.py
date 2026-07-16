from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssigneeRuleConfigBase(BaseModel):
    name: str
    description: str | None = None
    requirement_owner_roles: str = ""
    task_owner_roles: str = ""
    test_case_tester_roles: str = ""
    test_run_owner_roles: str = ""
    bug_owner_roles: str = ""


class AssigneeRuleConfigCreate(AssigneeRuleConfigBase):
    model_config = ConfigDict(extra="forbid")


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

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
    enabled: bool = True


class AssigneeRuleConfigCreate(AssigneeRuleConfigBase):
    pass


class AssigneeRuleConfigUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    requirement_owner_roles: str | None = None
    task_owner_roles: str | None = None
    test_case_tester_roles: str | None = None
    test_run_owner_roles: str | None = None
    bug_owner_roles: str | None = None
    enabled: bool | None = None


class AssigneeRuleConfigRead(AssigneeRuleConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    create_time: datetime | None = None
    update_time: datetime | None = None

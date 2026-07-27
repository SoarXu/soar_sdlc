from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BusinessComponentCreateFromProject(BaseModel):
    source_project_id: int
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None


class BusinessComponentMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    component_role: str
    enabled: bool


class BusinessComponentMemberWrite(BaseModel):
    user_id: int
    component_role: str = Field(min_length=1, max_length=64)


class BusinessComponentTransitionRouteWrite(BaseModel):
    object_type: str = Field(pattern="^(requirement|task|bug)$")
    transition_id: int
    eligible_member_mode: str = Field(default="component_role", pattern="^(all|component_role|users)$")
    eligible_roles: str = ""
    eligible_user_ids: str = ""
    next_owner_mode: str = Field(default="component_role", pattern="^(keep_current|component_role|user|manual|pending_assignment)$")
    next_owner_roles: str = ""
    next_owner_user_id: int | None = None
    fallback_mode: str = Field(default="project_rule", pattern="^(project_rule|keep_current|pending_assignment)$")
    enabled: bool = True


class BusinessComponentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    owner_id: int | None = None
    workflow_scheme_id: int | None = None
    enabled: bool | None = None


class WorkflowMigrationRequest(BaseModel):
    new_definition_id: int
    new_state_id: int
    reason: str = Field(min_length=1)


class BusinessComponentReferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_project_id: int | None = None
    source_project_name_snapshot: str | None = None


class BusinessComponentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    source_project_id: int | None = None
    source_project_name_snapshot: str | None = None
    name: str
    description: str | None = None
    owner_id: int | None = None
    workflow_scheme_id: int | None = None
    enabled: bool
    members: list[BusinessComponentMemberRead] = []
    create_time: datetime | None = None
    update_time: datetime | None = None

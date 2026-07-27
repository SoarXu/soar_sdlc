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

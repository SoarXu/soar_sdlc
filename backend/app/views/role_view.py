from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RoleBase(BaseModel):
    role_key: str
    role_name: str
    description: str | None = None
    enabled: bool = True


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    role_name: str | None = None
    description: str | None = None
    enabled: bool | None = None


class RoleRead(RoleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_system: bool = False
    create_time: datetime | None = None
    update_time: datetime | None = None


class UserRoleAssignRequest(BaseModel):
    role_ids: list[int]

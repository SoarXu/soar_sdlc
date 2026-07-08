from pydantic import BaseModel, ConfigDict

from app.views.role_view import RoleRead


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    is_active: bool
    email: str | None = None
    mobile: str | None = None
    department: str | None = None
    must_change_password: bool = False
    roles: list[RoleRead] = []


class UserCreate(BaseModel):
    username: str
    full_name: str
    email: str | None = None
    mobile: str | None = None
    department: str | None = None
    role_ids: list[int] = []


class UserPasswordResponse(BaseModel):
    user: UserRead
    initial_password: str

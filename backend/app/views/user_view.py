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
    roles: list[RoleRead] = []

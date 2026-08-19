from pydantic import BaseModel, ConfigDict

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
    is_system_admin: bool = False


class UserCreate(BaseModel):
    username: str
    full_name: str
    email: str | None = None
    mobile: str | None = None
    department: str | None = None
    is_system_admin: bool = False


class UserSystemAdminUpdate(BaseModel):
    is_system_admin: bool


class UserPasswordResponse(BaseModel):
    user: UserRead
    initial_password: str

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    is_active: bool
    email: str | None = None
    mobile: str | None = None
    department: str | None = None
    employee_no: str | None = Field(default=None, max_length=64)
    auth_source: Literal["local", "ldap"] = "local"
    must_change_password: bool = False
    is_system_admin: bool = False


class UserCreate(BaseModel):
    username: str
    full_name: str
    email: str | None = None
    mobile: str | None = None
    department: str | None = None
    employee_no: str | None = Field(default=None, max_length=64)
    is_system_admin: bool = False

    @model_validator(mode="before")
    @classmethod
    def reject_auth_source(cls, value):
        if isinstance(value, dict) and "auth_source" in value:
            raise ValueError("Authentication source cannot be selected when creating a user")
        return value


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None
    mobile: str | None = None
    department: str | None = None
    employee_no: str | None = Field(default=None, max_length=64)


class UserSystemAdminUpdate(BaseModel):
    is_system_admin: bool


class UserPasswordResponse(BaseModel):
    user: UserRead
    initial_password: str

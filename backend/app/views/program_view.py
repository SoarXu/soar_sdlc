from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProgramBase(BaseModel):
    name: str
    parent_id: int | None = None
    owner_id: int | None = None
    department: str | None = None
    status: str = "active"
    description: str | None = None


class ProgramCreate(ProgramBase):
    pass


class ProgramUpdate(BaseModel):
    name: str | None = None
    parent_id: int | None = None
    owner_id: int | None = None
    department: str | None = None
    status: str | None = None
    description: str | None = None
    updater_id: int | None = None


class ProgramRead(ProgramBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creator_id: int | None = None
    updater_id: int | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None
    delete_time: datetime | None = None


class ProgramProjectRead(BaseModel):
    id: int
    name: str
    owner_id: int | None = None
    status: str


class ProgramTreeRead(ProgramRead):
    children: list[ProgramTreeRead] = []
    projects: list[ProgramProjectRead] = []

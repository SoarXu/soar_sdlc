from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ProgramBase(BaseModel):
    name: str
    parent_id: int | None = None
    owner_id: int | None = None
    department: str | None = None
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    is_long_term: bool = False
    status: str = "planning"
    description: str | None = None


class ProgramCreate(ProgramBase):
    pass


class ProgramUpdate(BaseModel):
    name: str | None = None
    parent_id: int | None = None
    owner_id: int | None = None
    department: str | None = None
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    is_long_term: bool | None = None
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
    parent_id: int | None = None
    program_id: int | None = None
    name: str
    owner_id: int | None = None
    status: str
    start_date: date | None = None
    end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    is_long_term: bool = False


class ProgramStatusOption(BaseModel):
    label: str
    value: str


class ProgramTreeRead(ProgramRead):
    node_type: str | None = None
    program_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    children: list[ProgramTreeRead] = []
    projects: list[ProgramProjectRead] = []

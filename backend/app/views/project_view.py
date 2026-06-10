from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ProjectBase(BaseModel):
    name: str
    program_id: int | None = None
    owner_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_long_term: bool = False
    status: str = "planning"
    description: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    program_id: int | None = None
    name: str | None = None
    owner_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_long_term: bool | None = None
    description: str | None = None
    workflow_config_id: int | None = None
    updater_id: int | None = None


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_config_id: int | None = None
    creator_id: int | None = None
    updater_id: int | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None
    delete_time: datetime | None = None

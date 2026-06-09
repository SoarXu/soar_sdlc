from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class IterationBase(BaseModel):
    project_id: int
    name: str
    owner_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str = "planning"
    goal: str | None = None


class IterationCreate(IterationBase):
    pass


class IterationUpdate(BaseModel):
    project_id: int | None = None
    name: str | None = None
    owner_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    goal: str | None = None
    updater_id: int | None = None


class IterationRead(IterationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creator_id: int | None = None
    updater_id: int | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None
    delete_time: datetime | None = None

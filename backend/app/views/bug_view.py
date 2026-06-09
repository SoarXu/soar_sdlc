from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BugBase(BaseModel):
    project_id: int
    requirement_id: int | None = None
    task_id: int | None = None
    test_case_id: int | None = None
    test_run_id: int | None = None
    title: str
    severity: str = "medium"
    priority: str = "medium"
    owner_id: int | None = None
    reporter_id: int | None = None
    reproduce_steps: str | None = None
    expected_result: str | None = None
    actual_result: str | None = None
    status: str = "open"


class BugCreate(BugBase):
    pass


class BugUpdate(BaseModel):
    project_id: int | None = None
    requirement_id: int | None = None
    task_id: int | None = None
    test_case_id: int | None = None
    test_run_id: int | None = None
    title: str | None = None
    severity: str | None = None
    priority: str | None = None
    owner_id: int | None = None
    reporter_id: int | None = None
    reproduce_steps: str | None = None
    expected_result: str | None = None
    actual_result: str | None = None
    status: str | None = None
    updater_id: int | None = None


class BugFromTestRunCaseRequest(BaseModel):
    title: str
    severity: str = "medium"
    priority: str = "medium"
    reporter_id: int | None = None
    reproduce_steps: str | None = None
    expected_result: str | None = None
    actual_result: str | None = None


class BugRead(BugBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creator_id: int | None = None
    updater_id: int | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None
    delete_time: datetime | None = None

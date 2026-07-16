from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.views.task_view import LinkedTaskSummary


class TestRunBase(BaseModel):
    project_id: int
    iteration_id: int | None = None
    name: str
    test_owner_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str = "planning"
    lifecycle_phase: str | None = None
    remark: str | None = None


class TestRunCreate(TestRunBase):
    pass


class TestRunUpdate(BaseModel):
    project_id: int | None = None
    iteration_id: int | None = None
    name: str | None = None
    test_owner_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    lifecycle_phase: str | None = None
    remark: str | None = None
    updater_id: int | None = None


class TestRunRead(TestRunBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creator_id: int | None = None
    updater_id: int | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None
    delete_time: datetime | None = None
    linked_tasks: list[LinkedTaskSummary] = Field(default_factory=list)


class SelectTestCasesRequest(BaseModel):
    test_case_ids: list[int]
    tester_id: int | None = None


class TestRunCaseUpdate(BaseModel):
    tester_id: int | None = None
    result: str | None = None
    execute_time: datetime | None = None
    remark: str | None = None


class TestRunCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    test_run_id: int
    test_case_id: int
    tester_id: int | None = None
    result: str
    execute_time: datetime | None = None
    remark: str | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None

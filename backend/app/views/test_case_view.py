from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.views.task_view import LinkedTaskSummary


class TestCaseBase(BaseModel):
    project_id: int | None = None
    requirement_id: int | None = None
    iteration_id: int | None = None
    title: str
    case_type: str | None = None
    test_scope: str | None = None
    default_tester_id: int | None = None
    precondition: str | None = None
    steps_json: dict | list | None = None
    expected_result: str | None = None
    lifecycle_phase: str | None = None


class TestCaseCreate(TestCaseBase):
    pass


class TestCaseUpdate(BaseModel):
    project_id: int | None = None
    requirement_id: int | None = None
    iteration_id: int | None = None
    title: str | None = None
    case_type: str | None = None
    test_scope: str | None = None
    default_tester_id: int | None = None
    precondition: str | None = None
    steps_json: dict | list | None = None
    expected_result: str | None = None
    lifecycle_phase: str | None = None
    updater_id: int | None = None


class TestCaseRead(TestCaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creator_id: int | None = None
    updater_id: int | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None
    delete_time: datetime | None = None
    last_execute_time: datetime | None = None
    last_execute_result: str | None = None
    linked_tasks: list[LinkedTaskSummary] = Field(default_factory=list)


class TestCaseExecutionCreate(BaseModel):
    executor_id: int | None = None
    execute_time: datetime | None = None
    steps_result_json: dict | list | None = None


class BugFromTestCaseRequest(BaseModel):
    title: str
    bug_type: str | None = None
    severity: str = "3"
    priority: str = "3"
    reporter_id: int | None = None
    reproduce_steps: str | None = None
    expected_result: str | None = None
    actual_result: str | None = None


class TestCaseExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    test_case_id: int
    executor_id: int | None = None
    execute_time: datetime
    result: str
    steps_result_json: dict | list | None = None
    create_time: datetime | None = None


class ValidationCaseRead(BaseModel):
    id: int
    project_id: int | None = None
    requirement_id: int | None = None
    iteration_id: int | None = None
    title: str
    case_type: str | None = None
    test_scope: str | None = None
    default_tester_id: int | None = None
    latest_execute_time: datetime | None = None
    latest_result: str | None = None
    open_bug_count: int = 0


class ValidationCaseSummary(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    blocked: int = 0
    ignored: int = 0
    pending: int = 0


class RequirementValidationCasesRead(BaseModel):
    summary: ValidationCaseSummary
    items: list[ValidationCaseRead]


class BugValidationContextRead(BaseModel):
    source: str
    requirement_id: int | None = None
    test_case_id: int | None = None
    summary: ValidationCaseSummary
    items: list[ValidationCaseRead]

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    programs: int
    projects: int
    requirements: int
    tasks: int
    open_bugs: int


class WorkbenchMoveRequest(BaseModel):
    object_type: str
    object_id: int
    target_iteration_id: int


class WorkbenchItem(BaseModel):
    id: int
    object_type: str
    title: str
    project_id: int | None = None
    project_name: str | None = None
    iteration_id: int | None = None
    owner_id: int | None = None
    status: str | None = None
    priority: str | None = None
    due_date: str | None = None
    last_execute_time: str | None = None
    last_execute_result: str | None = None
    requirement_id: int | None = None
    task_id: int | None = None
    test_case_id: int | None = None
    bug_type: str | None = None
    severity: str | None = None


class WorkbenchIteration(BaseModel):
    id: int
    name: str
    status: str
    owner_id: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    requirements: list[WorkbenchItem]
    tasks: list[WorkbenchItem]
    test_cases: list[WorkbenchItem]
    bugs: list[WorkbenchItem]
    counts: dict[str, int]


class WorkbenchResponse(BaseModel):
    iterations: list[WorkbenchIteration]
    owners: list[dict]

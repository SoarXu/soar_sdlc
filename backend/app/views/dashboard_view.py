from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    programs: int
    projects: int
    requirements: int
    tasks: int
    open_bugs: int


class WorkbenchItem(BaseModel):
    id: int
    object_type: str
    title: str
    project_id: int | None = None
    project_name: str | None = None
    iteration_id: int | None = None
    iteration_name: str | None = None
    lifecycle_phase: str | None = None
    owner_id: int | None = None
    handler_id: int | None = None
    iteration_group_key: str | None = None
    status: str | None = None
    current_state_id: int | None = None
    status_name: str | None = None
    state_category: str | None = None
    priority: str | None = None
    due_date: str | None = None
    last_execute_time: str | None = None
    last_execute_result: str | None = None
    steps_json: dict | list | None = None
    requirement_id: int | None = None
    task_id: int | None = None
    test_case_id: int | None = None
    bug_type: str | None = None
    severity: str | None = None
    create_time: str | None = None
    creator_id: int | None = None
    proposer_id: int | None = None
    reporter_id: int | None = None
    watch_source: str | None = None
    mentioned_in_comment_id: int | None = None
    exception_key: str | None = None
    exception_label: str | None = None
    exception_keys: list[str] = Field(default_factory=list)
    exception_details: list[dict] = Field(default_factory=list)
    entered_at: str | None = None
    threshold_hours: int | None = None
    threshold_count: int | None = None
    overdue_hours: float | None = None


class WorkbenchSection(BaseModel):
    label: str
    items: list[WorkbenchItem] = Field(default_factory=list)
    total: int = 0


class WorkbenchResponse(BaseModel):
    pending_handling: WorkbenchSection = Field(default_factory=lambda: WorkbenchSection(label="待处理"))
    unassigned: WorkbenchSection = Field(default_factory=lambda: WorkbenchSection(label="未分派"))
    created_by_me: WorkbenchSection = Field(default_factory=lambda: WorkbenchSection(label="我发起的"))
    watched_by_me: WorkbenchSection = Field(default_factory=lambda: WorkbenchSection(label="我关注的"))
    mentioned_me: WorkbenchSection = Field(default_factory=lambda: WorkbenchSection(label="提到我的"))
    exception_center: WorkbenchSection = Field(default_factory=lambda: WorkbenchSection(label="异常中心"))
    owners: list[dict] = Field(default_factory=list)
    review_tasks: list[dict] = Field(default_factory=list)
    role_keys: list[str] = Field(default_factory=list)
    view_mode: str = "all"

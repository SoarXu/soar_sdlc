from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.views.bug_view import BugRead
from app.views.iteration_view import IterationRead
from app.views.requirement_view import RequirementRead
from app.views.task_view import TaskRead
from app.views.test_case_view import TestCaseRead
from app.views.test_run_view import TestRunRead


class ProjectBase(BaseModel):
    name: str
    parent_id: int | None = None
    program_id: int | None = None
    owner_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    is_long_term: bool = False
    status: str = "planning"
    description: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    parent_id: int | None = None
    program_id: int | None = None
    name: str | None = None
    owner_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
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


class ProjectMemberBase(BaseModel):
    user_id: int
    project_role: str
    is_default_assignee: bool = False
    is_workbench_participant: bool = True
    sort_order: int = 0


class ProjectMemberCreate(ProjectMemberBase):
    pass


class ProjectMemberRead(ProjectMemberBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    join_time: datetime | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None


class ProjectIterationPage(BaseModel):
    items: list[IterationRead]
    total: int
    page: int
    page_size: int


class ProjectRequirementPage(BaseModel):
    items: list[RequirementRead]
    total: int
    page: int
    page_size: int


class ProjectTaskPage(BaseModel):
    items: list[TaskRead]
    total: int
    page: int
    page_size: int


class ProjectTestCasePage(BaseModel):
    items: list[TestCaseRead]
    total: int
    page: int
    page_size: int


class ProjectTestRunPage(BaseModel):
    items: list[TestRunRead]
    total: int
    page: int
    page_size: int


class ProjectBugPage(BaseModel):
    items: list[BugRead]
    total: int
    page: int
    page_size: int

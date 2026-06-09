from pydantic import BaseModel


class DashboardSummary(BaseModel):
    programs: int
    projects: int
    requirements: int
    tasks: int
    open_bugs: int

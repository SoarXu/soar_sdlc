from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.iteration import Iteration, IterationProject
from app.models.program import Program
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.user import User
from app.views.dashboard_view import DashboardSummary, WorkbenchItem, WorkbenchResponse


def get_dashboard_summary(db: Session) -> DashboardSummary:
    return DashboardSummary(
        programs=_count_active(db, Program),
        projects=_count_active(db, Project),
        requirements=_count_active(db, Requirement),
        tasks=_count_active(db, Task),
        open_bugs=db.query(func.count(Bug.id)).filter(Bug.deleted == 0, Bug.status != "closed").scalar()
        or 0,
    )


def get_workbench(db: Session) -> WorkbenchResponse:
    iterations = db.query(Iteration).filter(Iteration.deleted == 0).order_by(Iteration.id.desc()).all()
    iteration_ids = [item.id for item in iterations]
    iteration_phases = {item.id: item.lifecycle_phase for item in iterations}
    projects = {item.id: item for item in db.query(Project).filter(Project.deleted == 0).all()}
    iteration_projects = _iteration_projects(db, iteration_ids, projects)
    requirements = _items_by_iteration(
        [
            item for item in db.query(Requirement).filter(Requirement.deleted == 0, Requirement.iteration_id.in_(iteration_ids)).all()
            if _phase_matches(item, iteration_phases)
        ],
        lambda item: _requirement_item(item, projects),
    )
    tasks = _items_by_iteration(
        [
            item for item in db.query(Task).filter(Task.deleted == 0, Task.iteration_id.in_(iteration_ids)).all()
            if _phase_matches(item, iteration_phases)
        ],
        lambda item: _task_item(item, projects),
    )
    test_cases = _items_by_iteration(
        [
            item for item in db.query(TestCase).filter(TestCase.deleted == 0, TestCase.iteration_id.in_(iteration_ids)).all()
            if _phase_matches(item, iteration_phases)
        ],
        lambda item: _test_case_item(item, projects),
    )
    bugs = _items_by_iteration(
        [
            item for item in db.query(Bug).filter(Bug.deleted == 0, Bug.iteration_id.in_(iteration_ids)).all()
            if _phase_matches(item, iteration_phases)
        ],
        lambda item: _bug_item(item, projects),
    )

    owner_ids = {
        item.owner_id
        for group in [requirements, tasks, test_cases, bugs]
        for values in group.values()
        for item in values
        if item.owner_id
    }
    owners = [
        {"id": user.id, "full_name": user.full_name}
        for user in db.query(User).filter(User.deleted == 0, User.id.in_(owner_ids)).order_by(User.full_name.asc()).all()
    ] if owner_ids else []

    boards = []
    for iteration in iterations:
        reqs = requirements.get(iteration.id, [])
        task_items = tasks.get(iteration.id, [])
        case_items = test_cases.get(iteration.id, [])
        bug_items = bugs.get(iteration.id, [])
        boards.append({
            "id": iteration.id,
            "name": iteration.name,
            "status": iteration.status,
            "lifecycle_phase": iteration.lifecycle_phase,
            "owner_id": iteration.owner_id,
            "start_date": _date_value(iteration.start_date),
            "end_date": _date_value(iteration.end_date),
            "projects": iteration_projects.get(iteration.id, []),
            "requirements": reqs,
            "tasks": task_items,
            "test_cases": case_items,
            "bugs": bug_items,
            "counts": {
                "requirements": len(reqs),
                "tasks": len(task_items),
                "test_cases": len(case_items),
                "bugs": len(bug_items),
            },
        })
    return WorkbenchResponse(iterations=boards, owners=owners)


def move_workbench_item(db: Session, object_type: str, object_id: int, target_iteration_id: int) -> WorkbenchItem:
    iteration = db.query(Iteration).filter(Iteration.id == target_iteration_id, Iteration.deleted == 0).first()
    if not iteration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标迭代不存在")
    model_map = {
        "requirement": Requirement,
        "task": Task,
        "test_case": TestCase,
        "bug": Bug,
    }
    model = model_map.get(object_type)
    if not model:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的工作项类型")
    item = db.query(model).filter(model.id == object_id, model.deleted == 0).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工作项不存在")
    if item.project_id not in _iteration_scoped_project_ids(db, target_iteration_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="工作项不在目标迭代的项目范围内")
    item.iteration_id = target_iteration_id
    db.commit()
    db.refresh(item)
    projects = {project.id: project for project in db.query(Project).filter(Project.deleted == 0).all()}
    return _item_for_type(object_type, item, projects)


def _count_active(db: Session, model) -> int:
    return db.query(func.count(model.id)).filter(model.deleted == 0).scalar() or 0


def _items_by_iteration(items, mapper) -> dict[int, list[WorkbenchItem]]:
    result: dict[int, list[WorkbenchItem]] = {}
    for item in items:
        if item.iteration_id is None:
            continue
        result.setdefault(item.iteration_id, []).append(mapper(item))
    for values in result.values():
        values.sort(key=lambda item: item.id, reverse=True)
    return result


def _phase_matches(item, iteration_phases: dict[int, str]) -> bool:
    return item.iteration_id in iteration_phases and (item.lifecycle_phase or "development") == iteration_phases[item.iteration_id]


def _iteration_projects(db: Session, iteration_ids: list[int], projects: dict[int, Project]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = {iteration_id: [] for iteration_id in iteration_ids}
    if not iteration_ids:
        return result
    rows = db.query(IterationProject).filter(IterationProject.iteration_id.in_(iteration_ids)).all()
    for row in rows:
        project = projects.get(row.project_id)
        if project:
            result.setdefault(row.iteration_id, []).append({"id": project.id, "name": project.name})
    for values in result.values():
        values.sort(key=lambda item: item["name"])
    return result


def _iteration_scoped_project_ids(db: Session, iteration_id: int) -> set[int]:
    root_ids = [
        row.project_id for row in db.query(IterationProject).filter(IterationProject.iteration_id == iteration_id).all()
    ]
    result = set(root_ids)
    for project_id in root_ids:
        result.update(_collect_descendant_project_ids(db, project_id))
    return result


def _collect_descendant_project_ids(db: Session, project_id: int) -> set[int]:
    children = db.query(Project).filter(Project.parent_id == project_id, Project.deleted == 0).all()
    result = {child.id for child in children}
    for child in children:
        result.update(_collect_descendant_project_ids(db, child.id))
    return result


def _item_for_type(object_type: str, item, projects: dict[int, Project]) -> WorkbenchItem:
    if object_type == "requirement":
        return _requirement_item(item, projects)
    if object_type == "task":
        return _task_item(item, projects)
    if object_type == "test_case":
        return _test_case_item(item, projects)
    return _bug_item(item, projects)


def _requirement_item(item: Requirement, projects: dict[int, Project]) -> WorkbenchItem:
    return WorkbenchItem(
        id=item.id,
        object_type="requirement",
        title=item.title,
        project_id=item.project_id,
        project_name=_project_name(projects, item.project_id),
        iteration_id=item.iteration_id,
        lifecycle_phase=item.lifecycle_phase,
        owner_id=item.owner_id,
        status=item.status,
        priority=item.priority,
        requirement_id=item.id,
    )


def _task_item(item: Task, projects: dict[int, Project]) -> WorkbenchItem:
    return WorkbenchItem(
        id=item.id,
        object_type="task",
        title=item.title,
        project_id=item.project_id,
        project_name=_project_name(projects, item.project_id),
        iteration_id=item.iteration_id,
        lifecycle_phase=item.lifecycle_phase,
        owner_id=item.owner_id,
        status=item.status,
        priority=item.priority,
        due_date=_date_value(item.due_date),
        requirement_id=item.requirement_id,
    )


def _test_case_item(item: TestCase, projects: dict[int, Project]) -> WorkbenchItem:
    return WorkbenchItem(
        id=item.id,
        object_type="test_case",
        title=item.title,
        project_id=item.project_id,
        project_name=_project_name(projects, item.project_id),
        iteration_id=item.iteration_id,
        lifecycle_phase=item.lifecycle_phase,
        owner_id=item.default_tester_id,
        status=item.status,
        last_execute_time=_datetime_value(item.last_execute_time),
        last_execute_result=item.last_execute_result,
        steps_json=item.steps_json,
        requirement_id=item.requirement_id,
        test_case_id=item.id,
    )


def _bug_item(item: Bug, projects: dict[int, Project]) -> WorkbenchItem:
    return WorkbenchItem(
        id=item.id,
        object_type="bug",
        title=item.title,
        project_id=item.project_id,
        project_name=_project_name(projects, item.project_id),
        iteration_id=item.iteration_id,
        lifecycle_phase=item.lifecycle_phase,
        owner_id=item.owner_id,
        status=item.status,
        priority=item.priority,
        requirement_id=item.requirement_id,
        task_id=item.task_id,
        test_case_id=item.test_case_id,
        bug_type=item.bug_type,
        severity=item.severity,
    )


def _project_name(projects: dict[int, Project], project_id: int | None) -> str | None:
    return projects.get(project_id).name if project_id in projects else None


def _date_value(value) -> str | None:
    return value.isoformat() if value else None


def _datetime_value(value) -> str | None:
    return value.isoformat() if value else None

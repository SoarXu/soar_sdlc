from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.devops import DevopsCodeReviewTask, DevopsCommit, DevopsCommitLink
from app.models.iteration import Iteration, IterationProject
from app.models.program import Program
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.role import Role, UserRole
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.user import User
from app.services.project_team_service import workbench_project_ids_for_user
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


def get_workbench(db: Session, user_id: int | None = None) -> WorkbenchResponse:
    role_keys = _role_keys_for_user(db, user_id)
    view_mode = _workbench_view_mode(role_keys)
    scoped_project_ids = workbench_project_ids_for_user(db, user_id) if user_id and view_mode != "all" else set()
    iterations = (
        db.query(Iteration)
        .filter(Iteration.deleted == 0, Iteration.status == "active")
        .order_by(Iteration.id.desc())
        .all()
    )
    if user_id and view_mode != "all" and not scoped_project_ids:
        iterations = []
    iteration_ids = [item.id for item in iterations]
    projects = {item.id: item for item in db.query(Project).filter(Project.deleted == 0).all()}
    iteration_projects = _iteration_projects(db, iteration_ids, projects)
    if scoped_project_ids:
        iterations = [
            iteration
            for iteration in iterations
            if any(item["id"] in scoped_project_ids for item in iteration_projects.get(iteration.id, []))
        ]
        iteration_ids = [item.id for item in iterations]
    requirements = _items_by_iteration(
        db.query(Requirement).filter(Requirement.deleted == 0, Requirement.iteration_id.in_(iteration_ids)).all(),
        lambda item: _requirement_item(item, projects),
    )
    requirement_iteration_ids = {
        item.requirement_id: iteration_id
        for iteration_id, values in requirements.items()
        for item in values
        if item.requirement_id
    }
    tasks = _items_by_iteration(
        db.query(Task).filter(Task.deleted == 0, Task.iteration_id.in_(iteration_ids)).all(),
        lambda item: _task_item(item, projects),
    )
    _merge_requirement_linked_items(
        tasks,
        db.query(Task).filter(Task.deleted == 0, Task.requirement_id.in_(requirement_iteration_ids)).all(),
        requirement_iteration_ids,
        lambda item, iteration_id: _task_item(item, projects, iteration_id),
    )
    test_cases = _items_by_iteration(
        db.query(TestCase).filter(TestCase.deleted == 0, TestCase.iteration_id.in_(iteration_ids)).all(),
        lambda item: _test_case_item(item, projects, marker=_test_case_marker(item, requirements)),
    )
    _merge_requirement_linked_items(
        test_cases,
        db.query(TestCase).filter(TestCase.deleted == 0, TestCase.requirement_id.in_(requirement_iteration_ids)).all(),
        requirement_iteration_ids,
        lambda item, iteration_id: _test_case_item(item, projects, iteration_id, _test_case_marker(item, requirements)),
    )
    bugs = _items_by_iteration(
        db.query(Bug).filter(Bug.deleted == 0, Bug.iteration_id.in_(iteration_ids)).all(),
        lambda item: _bug_item(item, projects),
    )

    review_tasks = _review_tasks(db)
    owner_ids = {
        item.owner_id
        for group in [requirements, tasks, test_cases, bugs]
        for values in group.values()
        for item in values
        if item.owner_id
    }
    owner_ids.update(item.get("owner_id") for item in review_tasks if item.get("owner_id"))
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
        reqs = _filter_items_for_role(reqs, user_id, view_mode, include_test_cases=False, scoped_project_ids=scoped_project_ids)
        task_items = _filter_items_for_role(task_items, user_id, view_mode, include_test_cases=False, scoped_project_ids=scoped_project_ids)
        case_items = _filter_items_for_role(case_items, user_id, view_mode, include_test_cases=True, scoped_project_ids=scoped_project_ids)
        bug_items = _filter_items_for_role(bug_items, user_id, view_mode, include_test_cases=False, scoped_project_ids=scoped_project_ids)
        boards.append({
            "id": iteration.id,
            "name": iteration.name,
            "status": iteration.status,
            "lifecycle_phase": iteration.lifecycle_phase,
            "owner_id": iteration.owner_id,
            "start_date": _date_value(iteration.start_date),
            "end_date": _date_value(iteration.end_date),
            "create_time": _datetime_value(iteration.create_time),
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
    review_tasks = _filter_review_tasks_for_role(review_tasks, user_id, view_mode)
    return WorkbenchResponse(iterations=boards, owners=owners, review_tasks=review_tasks, role_keys=role_keys, view_mode=view_mode)


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


def _merge_requirement_linked_items(result: dict[int, list[WorkbenchItem]], items, requirement_iteration_ids: dict[int, int], mapper) -> None:
    existing = {
        (item.object_type, item.id)
        for values in result.values()
        for item in values
    }
    for item in items:
        iteration_id = requirement_iteration_ids.get(item.requirement_id)
        if not iteration_id:
            continue
        workbench_item = mapper(item, iteration_id)
        if (workbench_item.object_type, workbench_item.id) in existing:
            continue
        result.setdefault(iteration_id, []).append(workbench_item)
        existing.add((workbench_item.object_type, workbench_item.id))
    for values in result.values():
        values.sort(key=lambda item: item.id, reverse=True)


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


def _review_tasks(db: Session) -> list[dict]:
    tasks = db.query(DevopsCodeReviewTask).order_by(DevopsCodeReviewTask.id.desc()).limit(100).all()
    commit_ids = [item.commit_id for item in tasks]
    commits = {
        item.id: item
        for item in db.query(DevopsCommit).filter(DevopsCommit.id.in_(commit_ids), DevopsCommit.deleted == 0).all()
    } if commit_ids else {}
    link_rows = db.query(DevopsCommitLink).filter(DevopsCommitLink.commit_id.in_(commit_ids)).all() if commit_ids else []
    links: dict[int, list[dict]] = {}
    for row in link_rows:
        links.setdefault(row.commit_id, []).append({"object_type": row.object_type, "object_id": row.object_id})
    result = []
    for task in tasks:
        commit = commits.get(task.commit_id)
        result.append({
            "id": task.id,
            "object_type": "code_review",
            "title": task.title,
            "owner_id": task.owner_id,
            "status": task.status,
            "commit_id": task.commit_id,
            "commit_sha": commit.commit_sha if commit else None,
            "short_sha": commit.short_sha if commit else None,
            "branch_name": commit.branch_name if commit else None,
            "author_name": commit.author_name if commit else None,
            "committed_at": _datetime_value(commit.committed_at) if commit else None,
            "links": links.get(task.commit_id, []),
        })
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


def _task_item(item: Task, projects: dict[int, Project], iteration_id: int | None = None) -> WorkbenchItem:
    return WorkbenchItem(
        id=item.id,
        object_type="task",
        title=item.title,
        project_id=item.project_id,
        project_name=_project_name(projects, item.project_id),
        iteration_id=iteration_id if iteration_id is not None else item.iteration_id,
        lifecycle_phase=item.lifecycle_phase,
        owner_id=item.owner_id,
        status=item.status,
        priority=item.priority,
        due_date=_date_value(item.due_date),
        requirement_id=item.requirement_id,
    )


def _test_case_item(
    item: TestCase,
    projects: dict[int, Project],
    iteration_id: int | None = None,
    marker: str | None = None,
) -> WorkbenchItem:
    return WorkbenchItem(
        id=item.id,
        object_type="test_case",
        title=item.title,
        project_id=item.project_id,
        project_name=_project_name(projects, item.project_id),
        iteration_id=iteration_id if iteration_id is not None else item.iteration_id,
        lifecycle_phase=item.lifecycle_phase,
        owner_id=item.default_tester_id,
        status=item.status,
        last_execute_time=_datetime_value(item.last_execute_time),
        last_execute_result=item.last_execute_result,
        steps_json=item.steps_json,
        requirement_id=item.requirement_id,
        test_case_id=item.id,
        marker=marker,
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


def _role_keys_for_user(db: Session, user_id: int | None) -> list[str]:
    if not user_id:
        return []
    rows = (
        db.query(Role.role_key)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id, Role.enabled.is_(True))
        .order_by(Role.id.asc())
        .all()
    )
    return [row.role_key for row in rows]


def _workbench_view_mode(role_keys: list[str]) -> str:
    role_set = set(role_keys)
    if "system_admin" in role_set:
        return "all"
    if role_set & {"project_owner", "product_manager", "development_lead"}:
        return "lead"
    if "tester" in role_set:
        return "tester"
    if "developer" in role_set:
        return "developer"
    return "all"


def _filter_items_for_role(
    items: list[WorkbenchItem],
    user_id: int | None,
    view_mode: str,
    include_test_cases: bool,
    scoped_project_ids: set[int] | None = None,
) -> list[WorkbenchItem]:
    if scoped_project_ids:
        return [item for item in items if item.project_id in scoped_project_ids]
    if view_mode in {"all", "lead"} or not user_id:
        return items
    if view_mode == "tester":
        return items
    if view_mode == "developer":
        return [] if include_test_cases else items
    return items


def _filter_review_tasks_for_role(review_tasks: list[dict], user_id: int | None, view_mode: str) -> list[dict]:
    if view_mode in {"all", "lead"} or not user_id:
        return review_tasks
    if view_mode == "developer":
        return [item for item in review_tasks if item.get("owner_id") == user_id]
    return []


def _test_case_marker(item: TestCase, requirements: dict[int, list[WorkbenchItem]]) -> str | None:
    requirement_items = {
        requirement.id: requirement
        for values in requirements.values()
        for requirement in values
    }
    requirement = requirement_items.get(item.requirement_id)
    if not requirement or requirement.status not in {"done", "closed"}:
        return None
    if item.last_execute_result == "passed":
        return "最近通过"
    if item.last_execute_result in {"failed", "blocked"}:
        return "最近失败"
    return "待回归"

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.iteration import Iteration, IterationProject
from app.models.bug import Bug
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.test_case import TestCase
from app.services.status_operation_service import create_status_operation, list_status_operations
from app.views.iteration_view import IterationCreate, IterationUpdate
from app.views.status_operation_view import StatusOperationCreate


def list_iterations(db: Session, project_id: int | None = None) -> list[dict]:
    query = db.query(Iteration).filter(Iteration.deleted == 0)
    if project_id:
        subquery = db.query(IterationProject.iteration_id).filter(IterationProject.project_id == project_id)
        query = query.filter(Iteration.id.in_(subquery))
    iterations = query.order_by(Iteration.id.desc()).all()

    result = []
    for it in iterations:
        ip_records = db.query(IterationProject).filter(IterationProject.iteration_id == it.id).all()
        project_ids = [ip.project_id for ip in ip_records]
        result.append({
            "id": it.id,
            "project_id": project_ids[0] if project_ids else None,
            "project_ids": project_ids,
            "name": it.name,
            "owner_id": it.owner_id,
            "start_date": it.start_date,
            "end_date": it.end_date,
            "actual_start_date": it.actual_start_date,
            "status": it.status,
            "goal": it.goal,
            "creator_id": it.creator_id,
            "updater_id": it.updater_id,
            "create_time": it.create_time,
            "update_time": it.update_time,
            "delete_time": it.delete_time,
        })
    return result


def create_iteration(db: Session, payload: IterationCreate) -> dict:
    data = payload.model_dump()
    project_id = data.pop("project_id", None)
    project_ids = data.pop("project_ids", [])
    if project_id and not project_ids:
        project_ids = [project_id]
    _validate_top_level_projects(db, project_ids)

    iteration = Iteration(**data)
    db.add(iteration)
    db.flush()

    for pid in project_ids:
        db.add(IterationProject(iteration_id=iteration.id, project_id=pid))
    db.commit()
    db.refresh(iteration)

    return {
        "id": iteration.id,
        "project_id": project_ids[0] if project_ids else None,
        "project_ids": project_ids,
        "name": iteration.name,
        "owner_id": iteration.owner_id,
        "start_date": iteration.start_date,
        "end_date": iteration.end_date,
        "actual_start_date": iteration.actual_start_date,
        "status": iteration.status,
        "goal": iteration.goal,
        "creator_id": iteration.creator_id,
        "updater_id": iteration.updater_id,
        "create_time": iteration.create_time,
        "update_time": iteration.update_time,
        "delete_time": iteration.delete_time,
    }


def update_iteration(db: Session, iteration_id: int, payload: IterationUpdate) -> dict:
    iteration = _get_active_iteration(db, iteration_id)
    data = payload.model_dump(exclude_unset=True)
    project_id = data.pop("project_id", None)
    project_ids = data.pop("project_ids", None)
    if project_id and project_ids is None:
        project_ids = [project_id]

    if project_ids is not None:
        _validate_top_level_projects(db, project_ids)
        db.query(IterationProject).filter(IterationProject.iteration_id == iteration_id).delete()
        for pid in project_ids:
            db.add(IterationProject(iteration_id=iteration_id, project_id=pid))

    for field, value in data.items():
        setattr(iteration, field, value)
    db.commit()
    db.refresh(iteration)

    ip_records = db.query(IterationProject).filter(IterationProject.iteration_id == iteration.id).all()
    result_project_ids = [ip.project_id for ip in ip_records]

    return {
        "id": iteration.id,
        "project_id": result_project_ids[0] if result_project_ids else None,
        "project_ids": result_project_ids,
        "name": iteration.name,
        "owner_id": iteration.owner_id,
        "start_date": iteration.start_date,
        "end_date": iteration.end_date,
        "actual_start_date": iteration.actual_start_date,
        "status": iteration.status,
        "goal": iteration.goal,
        "creator_id": iteration.creator_id,
        "updater_id": iteration.updater_id,
        "create_time": iteration.create_time,
        "update_time": iteration.update_time,
        "delete_time": iteration.delete_time,
    }


def delete_iteration(db: Session, iteration_id: int) -> None:
    iteration = _get_active_iteration(db, iteration_id)
    iteration.deleted = 1
    iteration.delete_time = datetime.now()
    db.commit()


def start_iteration(db: Session, iteration_id: int, payload: StatusOperationCreate | None = None) -> dict:
    iteration = _get_active_iteration(db, iteration_id)
    if iteration.status != "planning":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有规划中的迭代可以开始")
    if not payload or not payload.effective_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择实际开始日期")
    from_status = iteration.status
    iteration.status = "active"
    iteration.actual_start_date = payload.effective_time.date()
    create_status_operation(
        db,
        object_type="iteration",
        object_id=iteration.id,
        action="start",
        from_status=from_status,
        to_status=iteration.status,
        payload=payload,
    )
    db.commit()
    db.refresh(iteration)
    return _iteration_to_dict(iteration, _iteration_project_ids(db, iteration.id))


def list_iteration_status_operations(db: Session, iteration_id: int) -> list[dict]:
    _get_active_iteration(db, iteration_id)
    return list_status_operations(db, "iteration", iteration_id)


def get_iteration_detail(db: Session, iteration_id: int) -> dict:
    iteration = _get_active_iteration(db, iteration_id)
    project_ids = _iteration_project_ids(db, iteration_id)
    scoped_project_ids = _iteration_scoped_project_ids(db, iteration_id)
    requirements = _linked_requirements(db, iteration_id)
    requirement_ids = [item.id for item in requirements]
    requirement_task_query = db.query(Task).filter(Task.deleted == 0, Task.requirement_id.in_(requirement_ids))
    direct_task_query = db.query(Task).filter(Task.deleted == 0, Task.iteration_id == iteration_id)
    tasks_by_id = {task.id: task for task in [*requirement_task_query.all(), *direct_task_query.all()]}
    test_cases = (
        db.query(TestCase)
        .filter(TestCase.deleted == 0, TestCase.requirement_id.in_(requirement_ids))
        .order_by(TestCase.id.desc())
        .all()
        if requirement_ids else []
    )
    bugs = (
        db.query(Bug)
        .filter(Bug.deleted == 0, Bug.iteration_id == iteration_id)
        .order_by(Bug.id.desc())
        .all()
    )
    covered_requirement_ids = {case.requirement_id for case in test_cases if case.requirement_id}
    requirement_total = len(requirements)
    closed_requirement_total = len([item for item in requirements if item.status == "closed"])
    return {
        "iteration": _iteration_to_dict(iteration, project_ids),
        "projects": _projects_to_tree(db, project_ids),
        "requirements": [_model_to_dict(item) for item in requirements],
        "tasks": [_model_to_dict(item) for item in sorted(tasks_by_id.values(), key=lambda item: item.id, reverse=True)],
        "test_cases": [_model_to_dict(item) for item in test_cases],
        "bugs": [_model_to_dict(item) for item in bugs],
        "metrics": {
            "requirement_total": requirement_total,
            "closed_requirement_total": closed_requirement_total,
            "progress_rate": _rate(closed_requirement_total, requirement_total),
            "covered_requirement_total": len(covered_requirement_ids),
            "test_coverage_rate": _rate(len(covered_requirement_ids), requirement_total),
        },
        "scoped_project_ids": sorted(scoped_project_ids),
    }


def available_requirements(db: Session, iteration_id: int) -> list[Requirement]:
    scoped_project_ids = _iteration_scoped_project_ids(db, iteration_id)
    return (
        db.query(Requirement)
        .filter(
            Requirement.deleted == 0,
            Requirement.project_id.in_(scoped_project_ids),
            Requirement.iteration_id.is_(None),
        )
        .order_by(Requirement.id.desc())
        .all()
    )


def link_requirements(db: Session, iteration_id: int, requirement_ids: list[int]) -> list[Requirement]:
    _get_active_iteration(db, iteration_id)
    scoped_project_ids = _iteration_scoped_project_ids(db, iteration_id)
    requirements = db.query(Requirement).filter(Requirement.deleted == 0, Requirement.id.in_(requirement_ids)).all()
    if len(requirements) != len(set(requirement_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需求不存在")
    for requirement in requirements:
        if requirement.project_id not in scoped_project_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需求不在迭代项目范围内")
        if requirement.iteration_id and requirement.iteration_id != iteration_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需求已关联其他迭代")
        requirement.iteration_id = iteration_id
    db.commit()
    return _linked_requirements(db, iteration_id)


def unlink_requirement(db: Session, iteration_id: int, requirement_id: int) -> None:
    _get_active_iteration(db, iteration_id)
    requirement = db.query(Requirement).filter(Requirement.id == requirement_id, Requirement.deleted == 0).first()
    if requirement and requirement.iteration_id == iteration_id:
        requirement.iteration_id = None
        db.commit()


def available_tasks(db: Session, iteration_id: int) -> list[Task]:
    scoped_project_ids = _iteration_scoped_project_ids(db, iteration_id)
    return (
        db.query(Task)
        .filter(
            Task.deleted == 0,
            Task.project_id.in_(scoped_project_ids),
            Task.iteration_id.is_(None),
            Task.requirement_id.is_(None),
        )
        .order_by(Task.id.desc())
        .all()
    )


def link_tasks(db: Session, iteration_id: int, task_ids: list[int]) -> list[Task]:
    _get_active_iteration(db, iteration_id)
    scoped_project_ids = _iteration_scoped_project_ids(db, iteration_id)
    tasks = db.query(Task).filter(Task.deleted == 0, Task.id.in_(task_ids)).all()
    if len(tasks) != len(set(task_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务不存在")
    for task in tasks:
        if task.project_id not in scoped_project_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务不在迭代项目范围内")
        if task.iteration_id and task.iteration_id != iteration_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务已关联其他迭代")
        task.iteration_id = iteration_id
    db.commit()
    return db.query(Task).filter(Task.deleted == 0, Task.iteration_id == iteration_id).order_by(Task.id.desc()).all()


def unlink_task(db: Session, iteration_id: int, task_id: int) -> None:
    _get_active_iteration(db, iteration_id)
    task = db.query(Task).filter(Task.id == task_id, Task.deleted == 0).first()
    if task and task.iteration_id == iteration_id:
        task.iteration_id = None
        db.commit()


def _get_active_iteration(db: Session, iteration_id: int) -> Iteration:
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    if not iteration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Iteration not found")
    return iteration


def _iteration_to_dict(iteration: Iteration, project_ids: list[int]) -> dict:
    return {
        "id": iteration.id,
        "project_id": project_ids[0] if project_ids else None,
        "project_ids": project_ids,
        "name": iteration.name,
        "owner_id": iteration.owner_id,
        "start_date": iteration.start_date,
        "end_date": iteration.end_date,
        "actual_start_date": iteration.actual_start_date,
        "status": iteration.status,
        "goal": iteration.goal,
        "creator_id": iteration.creator_id,
        "updater_id": iteration.updater_id,
        "create_time": iteration.create_time,
        "update_time": iteration.update_time,
        "delete_time": iteration.delete_time,
    }


def _iteration_project_ids(db: Session, iteration_id: int) -> list[int]:
    return [
        item.project_id
        for item in db.query(IterationProject).filter(IterationProject.iteration_id == iteration_id).all()
    ]


def _iteration_scoped_project_ids(db: Session, iteration_id: int) -> set[int]:
    _get_active_iteration(db, iteration_id)
    result: set[int] = set()
    for project_id in _iteration_project_ids(db, iteration_id):
        result.add(project_id)
        result.update(_collect_descendant_project_ids(db, project_id))
    return result


def _collect_descendant_project_ids(db: Session, project_id: int) -> set[int]:
    children = db.query(Project).filter(Project.parent_id == project_id, Project.deleted == 0).all()
    result = {child.id for child in children}
    for child in children:
        result.update(_collect_descendant_project_ids(db, child.id))
    return result


def _linked_requirements(db: Session, iteration_id: int) -> list[Requirement]:
    return (
        db.query(Requirement)
        .filter(Requirement.deleted == 0, Requirement.iteration_id == iteration_id)
        .order_by(Requirement.project_id.asc(), Requirement.id.desc())
        .all()
    )


def _projects_to_tree(db: Session, root_project_ids: list[int]) -> list[dict]:
    roots = db.query(Project).filter(Project.deleted == 0, Project.id.in_(root_project_ids)).order_by(Project.id.asc()).all()
    return [_project_node(db, project) for project in roots]


def _project_node(db: Session, project: Project) -> dict:
    children = db.query(Project).filter(Project.deleted == 0, Project.parent_id == project.id).order_by(Project.id.asc()).all()
    return {
        "id": project.id,
        "name": project.name,
        "parent_id": project.parent_id,
        "children": [_project_node(db, child) for child in children],
    }


def _model_to_dict(model) -> dict:
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0


def _validate_top_level_projects(db: Session, project_ids: list[int]) -> None:
    if not project_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少需要绑定一个项目")
    for pid in project_ids:
        project = db.query(Project).filter(Project.id == pid, Project.deleted == 0).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"项目 {pid} 不存在")
        if project.parent_id is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"项目 '{project.name}' 是子项目，只能绑定顶级项目")

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
from app.views.iteration_view import IterationCreate, IterationUpdate


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


def _get_active_iteration(db: Session, iteration_id: int) -> Iteration:
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    if not iteration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Iteration not found")
    return iteration


def _validate_top_level_projects(db: Session, project_ids: list[int]) -> None:
    if not project_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="至少需要绑定一个项目")
    for pid in project_ids:
        project = db.query(Project).filter(Project.id == pid, Project.deleted == 0).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"项目 {pid} 不存在")
        if project.parent_id is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"项目 '{project.name}' 是子项目，只能绑定顶级项目")

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.iteration import Iteration
from app.views.iteration_view import IterationCreate, IterationUpdate


def list_iterations(db: Session) -> list[Iteration]:
    return db.query(Iteration).filter(Iteration.delete_time.is_(None)).order_by(Iteration.id.desc()).all()


def create_iteration(db: Session, payload: IterationCreate) -> Iteration:
    iteration = Iteration(**payload.model_dump())
    db.add(iteration)
    db.commit()
    db.refresh(iteration)
    return iteration


def update_iteration(db: Session, iteration_id: int, payload: IterationUpdate) -> Iteration:
    iteration = _get_active_iteration(db, iteration_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(iteration, field, value)
    db.commit()
    db.refresh(iteration)
    return iteration


def delete_iteration(db: Session, iteration_id: int) -> None:
    iteration = _get_active_iteration(db, iteration_id)
    iteration.delete_time = datetime.now()
    db.commit()


def _get_active_iteration(db: Session, iteration_id: int) -> Iteration:
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.delete_time.is_(None)).first()
    if not iteration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Iteration not found")
    return iteration

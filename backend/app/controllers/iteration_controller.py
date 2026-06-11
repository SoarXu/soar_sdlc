from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.iteration_service import create_iteration, delete_iteration, list_iterations, update_iteration
from app.views.iteration_view import IterationCreate, IterationRead, IterationUpdate


router = APIRouter()


@router.get("", response_model=list[IterationRead])
def get_iterations(project_id: int | None = None, db: Session = Depends(get_db)):
    return list_iterations(db, project_id)


@router.post("", response_model=IterationRead)
def post_iteration(payload: IterationCreate, db: Session = Depends(get_db)):
    return create_iteration(db, payload)


@router.patch("/{iteration_id}", response_model=IterationRead)
def patch_iteration(iteration_id: int, payload: IterationUpdate, db: Session = Depends(get_db)):
    return update_iteration(db, iteration_id, payload)


@router.delete("/{iteration_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_iteration(iteration_id: int, db: Session = Depends(get_db)):
    delete_iteration(db, iteration_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

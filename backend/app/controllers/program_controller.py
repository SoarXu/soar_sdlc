from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.program_service import (
    activate_program,
    close_program,
    create_program,
    delete_program,
    list_program_status_operations,
    list_program_status_options,
    list_program_tree,
    list_programs,
    start_program,
    suspend_program,
    update_program,
)
from app.views.program_view import ProgramCreate, ProgramRead, ProgramStatusOption, ProgramTreeRead, ProgramUpdate
from app.views.status_operation_view import StatusOperationCreate, StatusOperationRead


router = APIRouter()


@router.get("", response_model=list[ProgramRead])
def get_programs(db: Session = Depends(get_db)):
    return list_programs(db)


@router.get("/tree", response_model=list[ProgramTreeRead])
def get_program_tree(db: Session = Depends(get_db)):
    return list_program_tree(db)


@router.get("/status-options", response_model=list[ProgramStatusOption])
def get_program_status_options():
    return list_program_status_options()


@router.post("", response_model=ProgramRead)
def post_program(payload: ProgramCreate, db: Session = Depends(get_db)):
    return create_program(db, payload)


@router.patch("/{program_id}", response_model=ProgramRead)
def patch_program(program_id: int, payload: ProgramUpdate, db: Session = Depends(get_db)):
    return update_program(db, program_id, payload)


@router.get("/{program_id}/status-operations", response_model=list[StatusOperationRead])
def get_program_status_operations(program_id: int, db: Session = Depends(get_db)):
    return list_program_status_operations(db, program_id)


@router.post("/{program_id}/start", response_model=ProgramRead)
def start_program_status(
    program_id: int,
    payload: StatusOperationCreate | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return start_program(db, program_id, payload, actor_id=current_user.id if current_user else None)


@router.post("/{program_id}/suspend", response_model=ProgramRead)
def suspend_program_status(
    program_id: int,
    payload: StatusOperationCreate | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return suspend_program(db, program_id, payload, actor_id=current_user.id if current_user else None)


@router.post("/{program_id}/close", response_model=ProgramRead)
def close_program_status(
    program_id: int,
    payload: StatusOperationCreate | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return close_program(db, program_id, payload, actor_id=current_user.id if current_user else None)


@router.post("/{program_id}/activate", response_model=ProgramRead)
def activate_program_status(
    program_id: int,
    payload: StatusOperationCreate | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return activate_program(db, program_id, payload, actor_id=current_user.id if current_user else None)


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_program(program_id: int, db: Session = Depends(get_db)):
    delete_program(db, program_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

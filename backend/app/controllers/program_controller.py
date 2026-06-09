from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.program_service import create_program, delete_program, list_program_tree, list_programs, update_program
from app.views.program_view import ProgramCreate, ProgramRead, ProgramTreeRead, ProgramUpdate


router = APIRouter()


@router.get("", response_model=list[ProgramRead])
def get_programs(db: Session = Depends(get_db)):
    return list_programs(db)


@router.get("/tree", response_model=list[ProgramTreeRead])
def get_program_tree(db: Session = Depends(get_db)):
    return list_program_tree(db)


@router.post("", response_model=ProgramRead)
def post_program(payload: ProgramCreate, db: Session = Depends(get_db)):
    return create_program(db, payload)


@router.patch("/{program_id}", response_model=ProgramRead)
def patch_program(program_id: int, payload: ProgramUpdate, db: Session = Depends(get_db)):
    return update_program(db, program_id, payload)


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_program(program_id: int, db: Session = Depends(get_db)):
    delete_program(db, program_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

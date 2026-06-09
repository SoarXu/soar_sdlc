from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.program import Program
from app.views.program_view import ProgramCreate, ProgramUpdate


def list_programs(db: Session) -> list[Program]:
    return db.query(Program).filter(Program.delete_time.is_(None)).order_by(Program.id.desc()).all()


def create_program(db: Session, payload: ProgramCreate) -> Program:
    program = Program(**payload.model_dump())
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


def update_program(db: Session, program_id: int, payload: ProgramUpdate) -> Program:
    program = _get_active_program(db, program_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(program, field, value)
    db.commit()
    db.refresh(program)
    return program


def delete_program(db: Session, program_id: int) -> None:
    program = _get_active_program(db, program_id)
    program.delete_time = datetime.now()
    db.commit()


def _get_active_program(db: Session, program_id: int) -> Program:
    program = db.query(Program).filter(Program.id == program_id, Program.delete_time.is_(None)).first()
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program

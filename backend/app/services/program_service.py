from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.program import Program
from app.models.project import Project
from app.views.program_view import ProgramCreate, ProgramUpdate

PROGRAM_STATUS_OPTIONS = [
    {"label": "规划中", "value": "planning"},
    {"label": "进行中", "value": "active"},
    {"label": "长期维护", "value": "maintenance"},
    {"label": "已暂停", "value": "paused"},
    {"label": "已关闭", "value": "closed"},
]


def list_programs(db: Session) -> list[Program]:
    return db.query(Program).filter(Program.delete_time.is_(None)).order_by(Program.id.desc()).all()


def list_program_status_options() -> list[dict[str, str]]:
    return PROGRAM_STATUS_OPTIONS


def list_program_tree(db: Session) -> list[dict]:
    programs = db.query(Program).filter(Program.delete_time.is_(None)).order_by(Program.id.asc()).all()
    projects = db.query(Project).filter(Project.delete_time.is_(None)).order_by(Project.id.asc()).all()

    nodes = {
        program.id: {
            "id": program.id,
            "parent_id": program.parent_id,
            "name": program.name,
            "owner_id": program.owner_id,
            "department": program.department,
            "planned_start_date": program.planned_start_date,
            "planned_end_date": program.planned_end_date,
            "is_long_term": program.is_long_term,
            "status": program.status,
            "description": program.description,
            "creator_id": program.creator_id,
            "updater_id": program.updater_id,
            "create_time": program.create_time,
            "update_time": program.update_time,
            "delete_time": program.delete_time,
            "children": [],
            "projects": [],
        }
        for program in programs
    }

    for project in projects:
        if project.program_id in nodes:
            nodes[project.program_id]["projects"].append(
                {
                    "id": project.id,
                    "name": project.name,
                    "owner_id": project.owner_id,
                    "status": project.status,
                }
            )

    roots = []
    for program in programs:
        node = nodes[program.id]
        if program.parent_id and program.parent_id in nodes:
            nodes[program.parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


def create_program(db: Session, payload: ProgramCreate) -> Program:
    data = payload.model_dump()
    if data.get("is_long_term"):
        data["planned_end_date"] = None
    program = Program(**data)
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


def update_program(db: Session, program_id: int, payload: ProgramUpdate) -> Program:
    program = _get_active_program(db, program_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("is_long_term"):
        data["planned_end_date"] = None
    for field, value in data.items():
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

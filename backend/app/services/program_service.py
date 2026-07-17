from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.program import Program
from app.models.project import Project
from app.services.status_operation_service import create_status_operation, list_status_operations
from app.services.workflow_state_query_service import non_terminal_state_clause
from app.views.program_view import ProgramCreate, ProgramUpdate
from app.views.status_operation_view import StatusOperationCreate

PROGRAM_STATUS_OPTIONS = [
    {"label": "规划中", "value": "planning"},
    {"label": "进行中", "value": "active"},
    {"label": "已挂起", "value": "paused"},
    {"label": "已关闭", "value": "closed"},
]


def list_programs(db: Session) -> list[Program]:
    return db.query(Program).filter(Program.deleted == 0).order_by(Program.id.desc()).all()


def list_program_status_options() -> list[dict[str, str]]:
    return PROGRAM_STATUS_OPTIONS


def list_program_tree(db: Session) -> list[dict]:
    programs = db.query(Program).filter(Program.deleted == 0).order_by(Program.id.asc()).all()
    projects = db.query(Project).filter(Project.deleted == 0).order_by(Project.id.asc()).all()

    nodes = {
        program.id: {
            "id": program.id,
            "parent_id": program.parent_id,
            "name": program.name,
            "owner_id": program.owner_id,
            "department": program.department,
            "planned_start_date": program.planned_start_date,
            "planned_end_date": program.planned_end_date,
            "actual_start_date": program.actual_start_date,
            "actual_end_date": program.actual_end_date,
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
                    "parent_id": project.parent_id,
                    "program_id": project.program_id,
                    "name": project.name,
                    "owner_id": project.owner_id,
                    "workflow_definition_id": project.workflow_definition_id,
                    "current_state_id": project.current_state_id,
                    "status_name": project.status_name,
                    "state_category": project.state_category,
                    "start_date": project.start_date,
                    "end_date": project.end_date,
                    "actual_start_date": project.actual_start_date,
                    "actual_end_date": project.actual_end_date,
                    "is_long_term": project.is_long_term,
                }
            )

    roots = []
    for program in programs:
        node = nodes[program.id]
        if program.parent_id and program.parent_id in nodes:
            nodes[program.parent_id]["children"].append(node)
        else:
            roots.append(node)
    roots.extend(_build_unbound_project_tree(projects))
    return roots


def _project_tree_node(project: Project) -> dict:
    return {
        "id": project.id,
        "parent_id": project.parent_id,
        "program_id": project.program_id,
        "node_type": "project",
        "name": project.name,
        "owner_id": project.owner_id,
        "workflow_definition_id": project.workflow_definition_id,
        "current_state_id": project.current_state_id,
        "status_name": project.status_name,
        "state_category": project.state_category,
        "start_date": project.start_date,
        "end_date": project.end_date,
        "actual_start_date": project.actual_start_date,
        "actual_end_date": project.actual_end_date,
        "is_long_term": project.is_long_term,
        "children": [],
    }


def _build_unbound_project_tree(projects: list[Project]) -> list[dict]:
    nodes = {project.id: _project_tree_node(project) for project in projects if project.program_id is None}
    roots = []
    for project_id, node in nodes.items():
        parent_id = node["parent_id"]
        if parent_id and parent_id in nodes:
            nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


def create_program(db: Session, payload: ProgramCreate) -> Program:
    data = payload.model_dump()
    if data.get("is_long_term"):
        data["planned_end_date"] = None
    data["status"] = "planning"
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
    data.pop("status", None)
    for field, value in data.items():
        setattr(program, field, value)
    db.commit()
    db.refresh(program)
    return program


def delete_program(db: Session, program_id: int) -> None:
    program = _get_active_program(db, program_id)
    now = datetime.now()

    descendant_ids = _collect_descendant_program_ids(db, program_id)

    programs_to_delete = (
        db.query(Program)
        .filter(Program.id.in_(descendant_ids), Program.deleted == 0)
        .all()
    )
    for p in programs_to_delete:
        p.deleted = 1
        p.delete_time = now

    descendant_ids.add(program_id)
    projects_to_delete = (
        db.query(Project)
        .filter(Project.program_id.in_(descendant_ids), Project.deleted == 0)
        .all()
    )
    for p in projects_to_delete:
        p.deleted = 1
        p.delete_time = now

    program.deleted = 1
    program.delete_time = now
    db.commit()


def start_program(db: Session, program_id: int, payload: StatusOperationCreate | None = None, actor_id: int | None = None) -> Program:
    program = _get_active_program(db, program_id)
    _require_status(program.status, {"planning", "paused"}, "只有规划中或已挂起的项目集可以启动")
    from_status = program.status
    program.status = "active"
    if from_status == "planning":
        _require_effective_time(payload, "请选择实际开始日期")
        program.actual_start_date = _effective_date(payload)
    _activate_ancestor_programs(db, program.parent_id)
    create_status_operation(
        db,
        object_type="program",
        object_id=program.id,
        action="start",
        from_status=from_status,
        to_status=program.status,
        payload=payload,
        actor_id=actor_id,
    )
    db.commit()
    db.refresh(program)
    return program


def suspend_program(db: Session, program_id: int, payload: StatusOperationCreate | None = None, actor_id: int | None = None) -> Program:
    program = _get_active_program(db, program_id)
    _require_status(program.status, {"active"}, "只有进行中的项目集可以挂起")
    from_status = program.status
    program.status = "paused"
    create_status_operation(
        db,
        object_type="program",
        object_id=program.id,
        action="suspend",
        from_status=from_status,
        to_status=program.status,
        payload=payload,
        actor_id=actor_id,
    )
    db.commit()
    db.refresh(program)
    return program


def close_program(db: Session, program_id: int, payload: StatusOperationCreate | None = None, actor_id: int | None = None) -> Program:
    program = _get_active_program(db, program_id)
    _require_status(program.status, {"active", "paused"}, "只有进行中或已挂起的项目集可以关闭")
    if _has_unclosed_children(db, program_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="存在子项目集或项目为未关闭状态")
    from_status = program.status
    program.status = "closed"
    _require_effective_time(payload, "请选择实际完成日期")
    program.actual_end_date = _effective_date(payload)
    create_status_operation(
        db,
        object_type="program",
        object_id=program.id,
        action="close",
        from_status=from_status,
        to_status=program.status,
        payload=payload,
        actor_id=actor_id,
    )
    db.commit()
    db.refresh(program)
    return program


def activate_program(db: Session, program_id: int, payload: StatusOperationCreate | None = None, actor_id: int | None = None) -> Program:
    program = _get_active_program(db, program_id)
    _require_status(program.status, {"closed"}, "只有已关闭的项目集可以激活")
    from_status = program.status
    program.status = "active"
    program.actual_end_date = None
    _activate_ancestor_programs(db, program.parent_id)
    create_status_operation(
        db,
        object_type="program",
        object_id=program.id,
        action="activate",
        from_status=from_status,
        to_status=program.status,
        payload=payload,
        actor_id=actor_id,
    )
    db.commit()
    db.refresh(program)
    return program


def list_program_status_operations(db: Session, program_id: int) -> list[dict]:
    _get_active_program(db, program_id)
    return list_status_operations(db, "program", program_id)


def _get_active_program(db: Session, program_id: int) -> Program:
    program = db.query(Program).filter(Program.id == program_id, Program.deleted == 0).first()
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program


def _require_status(current_status: str, allowed_statuses: set[str], message: str) -> None:
    if current_status not in allowed_statuses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _require_effective_time(payload: StatusOperationCreate | None, message: str) -> None:
    if not payload or not payload.effective_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _activate_ancestor_programs(db: Session, parent_id: int | None) -> None:
    while parent_id:
        parent = db.query(Program).filter(Program.id == parent_id, Program.deleted == 0).first()
        if not parent:
            return
        if parent.status != "active":
            parent.status = "active"
        parent_id = parent.parent_id


def _has_unclosed_children(db: Session, program_id: int) -> bool:
    child_programs = db.query(Program).filter(Program.parent_id == program_id, Program.deleted == 0).all()
    if any(child.status != "closed" for child in child_programs):
        return True
    for child in child_programs:
        if _has_unclosed_children(db, child.id):
            return True

    return (
        db.query(Project)
        .filter(
            Project.program_id == program_id,
            Project.deleted == 0,
            non_terminal_state_clause(Project),
        )
        .first()
        is not None
    )


def _effective_date(payload: StatusOperationCreate | None) -> date:
    if payload and payload.effective_time:
        return payload.effective_time.date()
    return date.today()


def _collect_descendant_program_ids(db: Session, program_id: int) -> set[int]:
    result: set[int] = set()
    children = db.query(Program).filter(Program.parent_id == program_id, Program.deleted == 0).all()
    for child in children:
        result.add(child.id)
        result.update(_collect_descendant_program_ids(db, child.id))
    return result

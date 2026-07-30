from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.program import Program
from app.models.project import Project
from app.models.role import Role, UserRole
from app.models.user import User
from app.services.workflow_state_query_service import non_terminal_state_clause


def is_program_governor(db: Session, program_id: int | None, user_id: int | None) -> bool:
    """Return whether a user governs a program through active ownership ancestry."""
    if not program_id or user_id is None:
        return False

    user = (
        db.query(User)
        .filter(User.id == user_id, User.deleted == 0, User.is_active.is_(True))
        .first()
    )
    if not user:
        return False

    current_program_id = program_id
    visited_program_ids: set[int] = set()
    owner_ids: set[int] = set()
    while current_program_id is not None:
        if current_program_id in visited_program_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Program hierarchy cycle detected",
            )
        visited_program_ids.add(current_program_id)

        program = (
            db.query(Program)
            .filter(Program.id == current_program_id, Program.deleted == 0)
            .first()
        )
        if not program:
            return False
        if program.owner_id is not None:
            owner_ids.add(program.owner_id)
        current_program_id = program.parent_id

    if _is_system_admin(db, user_id):
        return True
    return user_id in owner_ids


def can_create_child_program(db: Session, parent_program_id: int | None, user_id: int | None) -> bool:
    return is_program_governor(db, parent_program_id, user_id)


def can_manage_program(db: Session, program_id: int | None, user_id: int | None) -> bool:
    return is_program_governor(db, program_id, user_id)


def can_delete_program(db: Session, program_id: int | None, user_id: int | None) -> bool:
    if not is_program_governor(db, program_id, user_id):
        return False
    assert program_id is not None
    assert user_id is not None

    if not _is_system_admin(db, user_id):
        return not _has_active_direct_children(db, program_id)

    subtree_programs = _collect_active_subtree_programs(db, program_id)
    program_ids = {program.id for program in subtree_programs}
    has_active_projects = bool(
        db.query(Project.id)
        .filter(Project.program_id.in_(program_ids), Project.deleted == 0)
        .first()
    )
    if len(program_ids) == 1 and not has_active_projects:
        return True

    if any(program.status != "closed" for program in subtree_programs):
        return False
    return not bool(
        db.query(Project.id)
        .filter(
            Project.program_id.in_(program_ids),
            Project.deleted == 0,
            non_terminal_state_clause(Project),
        )
        .first()
    )


def _has_active_direct_children(db: Session, program_id: int) -> bool:
    return bool(
        db.query(Program.id)
        .filter(Program.parent_id == program_id, Program.deleted == 0)
        .first()
        or db.query(Project.id)
        .filter(Project.program_id == program_id, Project.deleted == 0)
        .first()
    )


def _collect_active_subtree_programs(db: Session, program_id: int) -> list[Program]:
    root_program = (
        db.query(Program)
        .filter(Program.id == program_id, Program.deleted == 0)
        .first()
    )
    if not root_program:
        return []

    programs: list[Program] = []
    visited_program_ids: set[int] = set()
    current_level = [root_program]

    while current_level:
        current_level_ids = {program.id for program in current_level}
        if visited_program_ids & current_level_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Program hierarchy cycle detected",
            )
        visited_program_ids.update(current_level_ids)
        programs.extend(current_level)
        current_level = (
            db.query(Program)
            .filter(Program.parent_id.in_(current_level_ids), Program.deleted == 0)
            .all()
        )

    return programs


def _is_system_admin(db: Session, user_id: int) -> bool:
    return bool(
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(
            UserRole.user_id == user_id,
            Role.role_key == "system_admin",
            Role.enabled.is_(True),
        )
        .first()
    )

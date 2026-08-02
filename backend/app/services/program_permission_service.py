from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.program import Program
from app.models.role import Role, UserRole
from app.models.user import User


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
    return is_program_governor(db, program_id, user_id)


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

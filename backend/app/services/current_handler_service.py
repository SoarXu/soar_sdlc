from sqlalchemy.orm import Session

from app.models.user import User
from app.services.project_permission_service import (
    ensure_project_member,
    ensure_work_item_action_permission,
    ensure_work_item_assign_permission,
)


def ensure_current_handler(item, actor_id: int | None, object_label: str) -> None:
    if actor_id is None:
        return
    if item.owner_id == actor_id:
        return

    raise RuntimeError("ensure_current_handler requires db-aware permission checks; use ensure_work_item_action instead")


def ensure_work_item_action(db: Session, item, actor_id: int | None, object_label: str) -> None:
    ensure_work_item_action_permission(db, item, actor_id, object_label)


def ensure_assign_permission(db: Session, project_id: int | None, actor: User | None) -> None:
    ensure_work_item_assign_permission(db, project_id, actor)

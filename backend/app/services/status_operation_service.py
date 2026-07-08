from datetime import datetime

from sqlalchemy.orm import Session

from app.models.status_operation import StatusOperationLog
from app.models.user import User
from app.views.status_operation_view import StatusOperationCreate


ACTION_LABELS = {
    "start": "start",
    "suspend": "suspend",
    "close": "close",
    "activate": "activate",
}


def create_status_operation(
    db: Session,
    *,
    object_type: str,
    object_id: int,
    action: str,
    from_status: str | None,
    to_status: str,
    payload: StatusOperationCreate | None,
    actor_id: int | None = None,
    actor_name: str | None = None,
    is_delegated: bool = False,
    delegated_owner_id: int | None = None,
    delegated_owner_name: str | None = None,
    delegate_reason: str | None = None,
    selected_values: dict | None = None,
    default_target_status: str | None = None,
    resolved_target_status: str | None = None,
    override_reason: str | None = None,
    next_owner_id: int | None = None,
    next_owner_name: str | None = None,
    blocker_messages: list[str] | None = None,
) -> StatusOperationLog:
    effective_time = payload.effective_time if payload and payload.effective_time else datetime.now()
    reason = payload.reason if payload else None
    remark = payload.remark if payload else None
    operation = StatusOperationLog(
        object_type=object_type,
        object_id=object_id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        effective_time=effective_time,
        remark=remark,
        actor_id=actor_id,
        actor_name=actor_name,
        is_delegated=is_delegated,
        delegated_owner_id=delegated_owner_id,
        delegated_owner_name=delegated_owner_name,
        delegate_reason=delegate_reason or (getattr(payload, "delegate_reason", None) if payload else None),
        selected_values=selected_values or (getattr(payload, "selected_values", None) if payload else None),
        default_target_status=default_target_status or (getattr(payload, "default_target_status", None) if payload else None),
        resolved_target_status=resolved_target_status or (getattr(payload, "resolved_target_status", None) if payload else None),
        override_reason=override_reason or (getattr(payload, "override_reason", None) if payload else None),
        next_owner_id=next_owner_id or (getattr(payload, "next_owner_id", None) if payload else None),
        next_owner_name=next_owner_name or (getattr(payload, "next_owner_name", None) if payload else None),
        blocker_messages=blocker_messages or (getattr(payload, "blocker_messages", None) if payload else None),
    )
    db.add(operation)
    return operation


def list_status_operations(db: Session, object_type: str, object_id: int) -> list[dict]:
    operations = (
        db.query(StatusOperationLog)
        .filter(StatusOperationLog.object_type == object_type, StatusOperationLog.object_id == object_id)
        .order_by(StatusOperationLog.effective_time.asc(), StatusOperationLog.id.asc())
        .all()
    )
    actor_ids = {operation.actor_id for operation in operations if operation.actor_id}
    users = {}
    if actor_ids:
        users = {user.id: user.full_name for user in db.query(User).filter(User.id.in_(actor_ids)).all()}
    return [
        {
            "id": operation.id,
            "object_type": operation.object_type,
            "object_id": operation.object_id,
            "action": operation.action,
            "from_status": operation.from_status,
            "to_status": operation.to_status,
            "reason": operation.reason,
            "effective_time": operation.effective_time,
            "remark": operation.remark,
            "actor_id": operation.actor_id,
            "actor_name": operation.actor_name or (users.get(operation.actor_id) if operation.actor_id else "system"),
            "is_delegated": operation.is_delegated,
            "delegated_owner_id": operation.delegated_owner_id,
            "delegated_owner_name": operation.delegated_owner_name,
            "delegate_reason": operation.delegate_reason,
            "selected_values": operation.selected_values,
            "default_target_status": operation.default_target_status,
            "resolved_target_status": operation.resolved_target_status,
            "override_reason": operation.override_reason,
            "next_owner_id": operation.next_owner_id,
            "next_owner_name": operation.next_owner_name,
            "blocker_messages": operation.blocker_messages,
            "create_time": operation.create_time,
        }
        for operation in operations
    ]

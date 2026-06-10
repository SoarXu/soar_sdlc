from datetime import datetime

from sqlalchemy.orm import Session

from app.models.status_operation import StatusOperationLog
from app.models.user import User
from app.views.status_operation_view import StatusOperationCreate


ACTION_LABELS = {
    "start": "启动",
    "suspend": "挂起",
    "close": "关闭",
    "activate": "激活",
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
) -> StatusOperationLog:
    effective_time = payload.effective_time if payload and payload.effective_time else datetime.now()
    remark = payload.remark if payload else None
    operation = StatusOperationLog(
        object_type=object_type,
        object_id=object_id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        effective_time=effective_time,
        remark=remark,
        actor_id=actor_id,
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
            "effective_time": operation.effective_time,
            "remark": operation.remark,
            "actor_id": operation.actor_id,
            "actor_name": users.get(operation.actor_id) if operation.actor_id else "系统",
            "create_time": operation.create_time,
        }
        for operation in operations
    ]

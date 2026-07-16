from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.object_watch import ObjectWatch
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.user import User
from app.services.project_permission_service import ensure_audit_view_permission, ensure_authenticated
from app.views.object_watch_view import ObjectWatchRead, ObjectWatcherRead


MODEL_BY_TYPE = {
    "requirement": Requirement,
    "task": Task,
    "bug": Bug,
    "test_case": TestCase,
    "test_run": TestRun,
}


def get_watch_state(db: Session, object_type: str, object_id: int, actor: User | None) -> ObjectWatchRead:
    item = _get_item(db, object_type, object_id)
    ensure_audit_view_permission(db, _project_id(item), actor)
    return _watch_state(db, object_type, object_id, actor.id if actor else None)


def watch_object(db: Session, object_type: str, object_id: int, actor: User | None) -> ObjectWatchRead:
    ensure_authenticated(actor)
    item = _get_item(db, object_type, object_id)
    ensure_audit_view_permission(db, _project_id(item), actor)
    upsert_watch_source(db, object_type, object_id, actor.id, "manual")
    db.commit()
    return _watch_state(db, object_type, object_id, actor.id)


def unwatch_object(db: Session, object_type: str, object_id: int, actor: User | None) -> None:
    ensure_authenticated(actor)
    item = _get_item(db, object_type, object_id)
    ensure_audit_view_permission(db, _project_id(item), actor)
    disable_watches(db, object_type, object_id, actor.id)
    db.commit()


def upsert_watch_source(
    db: Session,
    object_type: str,
    object_id: int,
    user_id: int,
    source: str,
) -> ObjectWatch:
    watch = (
        db.query(ObjectWatch)
        .filter(
            ObjectWatch.object_type == object_type,
            ObjectWatch.object_id == object_id,
            ObjectWatch.user_id == user_id,
            ObjectWatch.source == source,
        )
        .first()
    )
    if watch:
        watch.enabled = True
        watch.update_time = datetime.now()
        return watch
    watch = ObjectWatch(
        object_type=object_type,
        object_id=object_id,
        user_id=user_id,
        source=source,
        enabled=True,
    )
    db.add(watch)
    db.flush()
    return watch


def disable_watches(db: Session, object_type: str, object_id: int, user_id: int) -> None:
    watches = (
        db.query(ObjectWatch)
        .filter(
            ObjectWatch.object_type == object_type,
            ObjectWatch.object_id == object_id,
            ObjectWatch.user_id == user_id,
            ObjectWatch.enabled == True,  # noqa: E712
        )
        .all()
    )
    for watch in watches:
        watch.enabled = False
        watch.update_time = datetime.now()


def _watch_state(db: Session, object_type: str, object_id: int, actor_user_id: int | None) -> ObjectWatchRead:
    rows = (
        db.query(ObjectWatch)
        .filter(
            ObjectWatch.object_type == object_type,
            ObjectWatch.object_id == object_id,
            ObjectWatch.enabled == True,  # noqa: E712
        )
        .order_by(ObjectWatch.update_time.desc(), ObjectWatch.id.desc())
        .all()
    )
    user_ids = {row.user_id for row in rows}
    users = {
        user.id: user
        for user in db.query(User).filter(User.id.in_(user_ids), User.deleted == 0).all()
    } if user_ids else {}
    watchers: list[ObjectWatcherRead] = []
    seen: set[int] = set()
    for row in rows:
        if row.user_id in seen:
            continue
        seen.add(row.user_id)
        user = users.get(row.user_id)
        watchers.append(
            ObjectWatcherRead(
                user_id=row.user_id,
                full_name=user.full_name if user else None,
                source=row.source,
                enabled=row.enabled,
                update_time=row.update_time,
            )
        )
    return ObjectWatchRead(
        object_type=object_type,
        object_id=object_id,
        watched=bool(actor_user_id and actor_user_id in seen),
        watcher_count=len(watchers),
        watchers=watchers,
    )


def _get_item(db: Session, object_type: str, object_id: int):
    model = MODEL_BY_TYPE.get(object_type)
    if not model:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported watch object type")
    item = db.query(model).filter(model.id == object_id, model.deleted == 0).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found")
    return item


def _project_id(item) -> int | None:
    if isinstance(item, Project):
        return item.id
    return getattr(item, "project_id", None)

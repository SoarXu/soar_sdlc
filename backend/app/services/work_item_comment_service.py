from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.user import User
from app.models.work_item_comment import WorkItemComment
from app.services.notification_service import create_mention_notifications
from app.services.object_watch_service import upsert_watch_source
from app.services.project_permission_service import ensure_audit_view_permission, ensure_authenticated
from app.views.work_item_comment_view import WorkItemCommentCreate, WorkItemCommentListRead, WorkItemCommentRead


MODEL_BY_TYPE = {
    "requirement": Requirement,
    "task": Task,
    "bug": Bug,
    "test_case": TestCase,
    "test_run": TestRun,
}


def list_comments(db: Session, object_type: str, object_id: int, actor: User | None) -> WorkItemCommentListRead:
    item = _get_item(db, object_type, object_id)
    ensure_audit_view_permission(db, getattr(item, "project_id", None), actor)
    comments = (
        db.query(WorkItemComment)
        .filter(WorkItemComment.object_type == object_type, WorkItemComment.object_id == object_id)
        .order_by(WorkItemComment.create_time.desc(), WorkItemComment.id.desc())
        .all()
    )
    return WorkItemCommentListRead(items=_comment_reads(db, comments))


def create_comment(db: Session, payload: WorkItemCommentCreate, actor: User | None) -> WorkItemCommentRead:
    ensure_authenticated(actor)
    item = _get_item(db, payload.object_type, payload.object_id)
    ensure_audit_view_permission(db, getattr(item, "project_id", None), actor)
    mentioned_user_ids = _normalized_mentioned_user_ids(payload.mentioned_user_ids)
    for user_id in mentioned_user_ids:
        _ensure_project_member_if_present(db, getattr(item, "project_id", None), user_id)

    mentioned_users = _mentioned_users(db, mentioned_user_ids)
    comment = WorkItemComment(
        object_type=payload.object_type,
        object_id=payload.object_id,
        author_id=actor.id,
        body=payload.body,
        mentioned_user_ids=mentioned_user_ids,
        mentions_metadata=[{"user_id": user.id, "display_name": user.full_name} for user in mentioned_users],
    )
    db.add(comment)
    db.flush()

    for user in mentioned_users:
        if user.id == actor.id:
            continue
        upsert_watch_source(db, payload.object_type, payload.object_id, user.id, "mention")
    create_mention_notifications(
        db,
        object_type=payload.object_type,
        object_id=payload.object_id,
        source_comment_id=comment.id,
        mentioned_user_ids=[user.id for user in mentioned_users],
        author=actor,
        body=payload.body,
    )
    db.commit()
    db.refresh(comment)
    return _comment_reads(db, [comment])[0]


def _comment_reads(db: Session, comments: list[WorkItemComment]) -> list[WorkItemCommentRead]:
    author_ids = {comment.author_id for comment in comments}
    users = {
        user.id: user.full_name
        for user in db.query(User).filter(User.id.in_(author_ids), User.deleted == 0).all()
    } if author_ids else {}
    return [
        WorkItemCommentRead(
            id=comment.id,
            object_type=comment.object_type,
            object_id=comment.object_id,
            author_id=comment.author_id,
            author_name=users.get(comment.author_id),
            body=comment.body,
            mentioned_user_ids=list(comment.mentioned_user_ids or []),
            mentions_metadata=list(comment.mentions_metadata or []),
            create_time=comment.create_time,
        )
        for comment in comments
    ]


def _get_item(db: Session, object_type: str, object_id: int):
    model = MODEL_BY_TYPE.get(object_type)
    if not model:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported comment object type")
    item = db.query(model).filter(model.id == object_id, model.deleted == 0).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found")
    return item


def _normalized_mentioned_user_ids(user_ids: list[int]) -> list[int]:
    normalized: list[int] = []
    for user_id in user_ids:
        if user_id not in normalized:
            normalized.append(user_id)
    return normalized


def _mentioned_users(db: Session, mentioned_user_ids: list[int]) -> list[User]:
    if not mentioned_user_ids:
        return []
    users = (
        db.query(User)
        .filter(User.id.in_(mentioned_user_ids), User.deleted == 0, User.is_active.is_(True))
        .all()
    )
    users_by_id = {user.id: user for user in users}
    missing_ids = [user_id for user_id in mentioned_user_ids if user_id not in users_by_id]
    if missing_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mentioned user not found")
    return [users_by_id[user_id] for user_id in mentioned_user_ids]


def _ensure_project_member_if_present(db: Session, project_id: int | None, user_id: int) -> None:
    if not project_id:
        return
    exists = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )
    if not exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mentioned user is not in project scope")

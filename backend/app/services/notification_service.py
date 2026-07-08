from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User


def list_notifications(db: Session, receiver_id: int) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.receiver_id == receiver_id)
        .order_by(Notification.create_time.desc(), Notification.id.desc())
        .all()
    )


def create_mention_notifications(
    db: Session,
    *,
    object_type: str,
    object_id: int,
    source_comment_id: int,
    mentioned_user_ids: list[int],
    author: User,
    body: str,
) -> list[Notification]:
    users = (
        db.query(User)
        .filter(User.id.in_(mentioned_user_ids), User.deleted == 0, User.is_active.is_(True))
        .all()
        if mentioned_user_ids
        else []
    )
    notifications: list[Notification] = []
    for user in users:
        if user.id == author.id:
            continue
        notification = Notification(
            receiver_id=user.id,
            title=f"{author.full_name} mentioned you",
            content=body,
            object_type=object_type,
            object_id=object_id,
            category="mention",
            source_type="work_item_comment",
            source_id=source_comment_id,
            metadata_json={"author_id": author.id, "author_name": author.full_name},
            is_read=False,
        )
        db.add(notification)
        notifications.append(notification)
    return notifications

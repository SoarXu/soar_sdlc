from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug_type import BugType
from app.views.bug_type_view import BugTypeCreate, BugTypeUpdate


DEFAULT_BUG_TYPES = [
    {"type_key": "code_issue", "display_name": "代码问题", "is_real_bug": True, "default_target_status": "fixing", "sort_order": 10},
    {"type_key": "configuration_issue", "display_name": "配置问题", "is_real_bug": True, "default_target_status": "fixing", "sort_order": 20},
    {"type_key": "data_issue", "display_name": "数据问题", "is_real_bug": True, "default_target_status": "fixing", "sort_order": 30},
    {"type_key": "environment_issue", "display_name": "环境问题", "is_real_bug": None, "default_target_status": "pending_verification", "sort_order": 40},
    {"type_key": "requirement_issue", "display_name": "需求问题", "is_real_bug": None, "default_target_status": "pending_verification", "sort_order": 50},
    {"type_key": "design_as_intended", "display_name": "设计如此", "is_real_bug": False, "default_target_status": "pending_verification", "sort_order": 60},
    {"type_key": "duplicate_issue", "display_name": "重复问题", "is_real_bug": False, "default_target_status": "pending_verification", "sort_order": 70},
    {"type_key": "cannot_reproduce", "display_name": "无法复现", "is_real_bug": False, "default_target_status": "pending_verification", "sort_order": 80},
    {"type_key": "operation_issue", "display_name": "操作问题", "is_real_bug": False, "default_target_status": "pending_verification", "sort_order": 90},
]


def ensure_default_bug_types(db: Session) -> None:
    existing_keys = {row.type_key for row in db.query(BugType.type_key).all()}
    missing = [BugType(**item) for item in DEFAULT_BUG_TYPES if item["type_key"] not in existing_keys]
    if not missing:
        return
    db.add_all(missing)
    db.commit()


def list_bug_types(db: Session, include_disabled: bool = False) -> list[BugType]:
    ensure_default_bug_types(db)
    query = db.query(BugType)
    if not include_disabled:
        query = query.filter(BugType.enabled.is_(True))
    return query.order_by(BugType.sort_order.asc(), BugType.id.asc()).all()


def bug_type_options(db: Session) -> list[dict]:
    return [
        {
            "label": item.display_name,
            "value": item.type_key,
            "is_real_bug": item.is_real_bug,
            "default_target_status": item.default_target_status,
        }
        for item in list_bug_types(db)
    ]


def get_enabled_bug_type(db: Session, type_key: str) -> BugType:
    ensure_default_bug_types(db)
    item = db.query(BugType).filter(BugType.type_key == type_key).first()
    if not item or not item.enabled:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Bug type is unavailable")
    return item


def create_bug_type(db: Session, payload: BugTypeCreate) -> BugType:
    if db.query(BugType).filter(BugType.type_key == payload.type_key).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bug type key already exists")
    item = BugType(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_bug_type(db: Session, bug_type_id: int, payload: BugTypeUpdate) -> BugType:
    item = _get_bug_type(db, bug_type_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    item.update_time = datetime.now()
    db.commit()
    db.refresh(item)
    return item


def _get_bug_type(db: Session, bug_type_id: int) -> BugType:
    item = db.query(BugType).filter(BugType.id == bug_type_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug type not found")
    return item

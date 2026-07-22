from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.exception_rule import ExceptionRule
from app.views.exception_rule_view import ExceptionRuleCreate, ExceptionRuleUpdate


DEFAULT_EXCEPTION_RULES = [
    ("unassigned_timeout", "未分派超时", "*", 24, None, 10),
    ("pending_timeout", "待处理超时", "*", 24, None, 20),
    ("fixing_timeout", "修复/处理超时", "bug", 24, None, 30),
    ("fixing_timeout", "修复/处理超时", "task", 24, None, 31),
    ("pending_verification_timeout", "待验证超时", "bug", 24, None, 40),
    ("verified_not_closed", "已验证未关闭", "bug", 24, None, 50),
    ("verification_failed", "验证失败", "bug", 0, None, 60),
    ("repeated_activation", "重复激活", "bug", None, 2, 70),
    ("high_priority_unprocessed", "高优先级未处理", "*", 4, None, 80),
    ("completed_requirement_active_bug", "已完成需求存在活动 Bug", "requirement", 0, None, 90),
    ("owner_required_missing", "Current state requires an owner", "*", 0, None, 100),
    ("owner_ineligible", "Current owner is ineligible", "*", 0, None, 101),
    ("iteration_history_inconsistent", "Iteration history is inconsistent", "*", 0, None, 102),
    ("missing_reactivation_audit", "Bug reactivation audit is missing", "bug", 0, None, 103),
]


def ensure_default_exception_rules(db: Session) -> list[ExceptionRule]:
    for key, label, object_type, hours, count, order in DEFAULT_EXCEPTION_RULES:
        exists = db.query(ExceptionRule).filter(
            ExceptionRule.exception_key == key,
            ExceptionRule.object_type == object_type,
            ExceptionRule.project_id.is_(None),
            ExceptionRule.priority.is_(None),
            ExceptionRule.status.is_(None),
        ).first()
        if not exists:
            db.add(
                ExceptionRule(
                    exception_key=key,
                    label=label,
                    object_type=object_type,
                    threshold_hours=hours,
                    threshold_count=count,
                    enabled=True,
                    sort_order=order,
                )
            )
    db.commit()
    return list_exception_rules(db)


def list_exception_rules(db: Session) -> list[ExceptionRule]:
    return db.query(ExceptionRule).order_by(ExceptionRule.sort_order.asc(), ExceptionRule.id.asc()).all()


def create_exception_rule(db: Session, payload: ExceptionRuleCreate, actor_id: int) -> ExceptionRule:
    rule = ExceptionRule(**payload.model_dump(), creator_id=actor_id)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_exception_rule(db: Session, rule_id: int, payload: ExceptionRuleUpdate, actor_id: int) -> ExceptionRule:
    rule = _get_rule(db, rule_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    rule.updater_id = actor_id
    db.commit()
    db.refresh(rule)
    return rule


def delete_exception_rule(db: Session, rule_id: int) -> None:
    rule = _get_rule(db, rule_id)
    db.delete(rule)
    db.commit()


def resolve_exception_rule(
    db: Session,
    exception_key: str,
    object_type: str,
    project_id: int | None,
    priority: str | None,
    current_state_id: int | None,
    current_state_name: str | None = None,
) -> ExceptionRule | None:
    candidates = db.query(ExceptionRule).filter(
        ExceptionRule.exception_key == exception_key,
        ExceptionRule.enabled.is_(True),
        ExceptionRule.object_type.in_(["*", object_type]),
    ).all()
    candidates = [
        item for item in candidates
        if item.project_id in {None, project_id}
        and item.priority in {None, priority}
        and item.status in {None, str(current_state_id) if current_state_id is not None else None}
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            int(item.project_id is not None),
            int(item.object_type == object_type),
            int(item.priority is not None),
            int(item.status is not None),
            -item.sort_order,
            item.id,
        ),
    )


def _get_rule(db: Session, rule_id: int) -> ExceptionRule:
    rule = db.query(ExceptionRule).filter(ExceptionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception rule not found")
    return rule

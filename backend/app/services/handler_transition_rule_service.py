from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.handler_transition_rule import HandlerTransitionRule
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.status_operation import StatusOperationLog
from app.services.status_operation_service import create_status_operation
from app.views.handler_transition_rule_view import (
    HandlerTransitionRuleCreate,
    HandlerTransitionRuleUpdate,
)


OBJECT_TYPES = {"requirement", "task", "bug"}
RULE_TYPES = {"advanced"}
TARGET_TYPES = {"project_role", "keep_current", "proposer", "reporter", "last_resolver", "none"}
FALLBACK_TYPES = {"keep_current", "project_role", "none"}


def list_rules(db: Session, config_id: int | None = None) -> list[HandlerTransitionRule]:
    query = db.query(HandlerTransitionRule)
    if config_id:
        query = query.filter(HandlerTransitionRule.config_id == config_id)
    query = query.filter(HandlerTransitionRule.rule_type == "advanced")
    return query.order_by(
        HandlerTransitionRule.config_id.asc(),
        HandlerTransitionRule.id.asc(),
    ).all()


def create_rule(db: Session, payload: HandlerTransitionRuleCreate) -> HandlerTransitionRule:
    data = _clean_payload(payload.model_dump())
    data["rule_type"] = data.get("rule_type") or "advanced"
    _validate_payload(db, data)
    rule = HandlerTransitionRule(**data)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(db: Session, rule_id: int, payload: HandlerTransitionRuleUpdate) -> HandlerTransitionRule:
    rule = _get_rule(db, rule_id)
    data = _clean_payload(payload.model_dump(exclude_unset=True))
    merged = {
        "config_id": rule.config_id,
        "rule_type": rule.rule_type,
        "object_type": rule.object_type,
        "action": rule.action,
        "from_status": rule.from_status,
        "to_status": rule.to_status,
        "target_type": rule.target_type,
        "target_roles": rule.target_roles,
        "fallback_type": rule.fallback_type,
        "fallback_roles": rule.fallback_roles,
        "enabled": rule.enabled,
        **data,
    }
    _validate_payload(db, merged, current_rule_id=rule_id)
    for field, value in data.items():
        setattr(rule, field, value)
    rule.update_time = datetime.now()
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule_id: int) -> None:
    rule = _get_rule(db, rule_id)
    rule.enabled = False
    rule.update_time = datetime.now()
    db.commit()


def apply_handler_transition(
    db: Session,
    *,
    item,
    object_type: str,
    action: str,
    from_status: str | None,
    to_status: str,
    actor_id: int | None = None,
) -> None:
    project_id = getattr(item, "source_project_id", None) or getattr(item, "project_id", None)
    config_id = _project_config_id(db, project_id)
    if not config_id:
        return
    rule = _matching_rule(db, config_id, object_type, action, from_status, to_status)
    if not rule:
        return
    original_owner_id = getattr(item, "owner_id", None)
    next_owner_id = _resolve_target_owner_id(db, item, project_id, rule)
    if next_owner_id is None:
        next_owner_id = _resolve_fallback_owner_id(db, project_id, rule, original_owner_id)
    if next_owner_id == original_owner_id:
        return
    item.owner_id = next_owner_id
    operation = create_status_operation(
        db,
        object_type=object_type,
        object_id=item.id,
        action="auto_assign",
        from_status=to_status,
        to_status=to_status,
        payload=None,
        actor_id=actor_id,
    )
    operation.remark = (
        f"handler auto transition: {original_owner_id} -> {next_owner_id}; "
        f"rule={rule.rule_type}:{rule.id}"
    )


def _get_rule(db: Session, rule_id: int) -> HandlerTransitionRule:
    rule = db.query(HandlerTransitionRule).filter(HandlerTransitionRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Handler transition rule not found")
    return rule


def _clean_payload(data: dict) -> dict:
    cleaned = dict(data)
    for field in ["rule_type", "object_type", "action", "from_status", "to_status", "target_type", "fallback_type"]:
        if field in cleaned and isinstance(cleaned[field], str):
            cleaned[field] = cleaned[field].strip()
    for field in ["target_roles", "fallback_roles"]:
        if field in cleaned and cleaned[field] is not None:
            cleaned[field] = ",".join(_split_csv(cleaned[field]))
    return cleaned


def _validate_payload(db: Session, data: dict, current_rule_id: int | None = None) -> None:
    _ensure_config_exists(db, data["config_id"])
    _validate_rule_data(data)

def _validate_rule_data(data: dict) -> None:
    if data["rule_type"] not in RULE_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown rule type")
    if data["object_type"] not in OBJECT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown object type")
    if not data.get("action"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Action is required")
    if data["target_type"] not in TARGET_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown target type")
    if data["fallback_type"] not in FALLBACK_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown fallback type")
    if data["target_type"] == "project_role" and not data.get("target_roles"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Target roles are required")
    if data["fallback_type"] == "project_role" and not data.get("fallback_roles"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Fallback roles are required")


def _ensure_config_exists(db: Session, config_id: int) -> None:
    if not db.query(AssigneeRuleConfig).filter(AssigneeRuleConfig.id == config_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignee rule config not found")


def _project_config_id(db: Session, project_id: int | None) -> int | None:
    if not project_id:
        return None
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    return project.assignee_rule_config_id if project else None


def _matching_rule(
    db: Session,
    config_id: int,
    object_type: str,
    action: str,
    from_status: str | None,
    to_status: str,
) -> HandlerTransitionRule | None:
    advanced_rules = (
        db.query(HandlerTransitionRule)
        .filter(
            HandlerTransitionRule.config_id == config_id,
            HandlerTransitionRule.rule_type == "advanced",
            HandlerTransitionRule.object_type == object_type,
            HandlerTransitionRule.action == action,
            HandlerTransitionRule.enabled == True,  # noqa: E712
        )
        .order_by(HandlerTransitionRule.id.asc())
        .all()
    )
    for rule in advanced_rules:
        if rule.from_status and rule.from_status != from_status:
            continue
        if rule.to_status and rule.to_status != to_status:
            continue
        return rule
    return None


def _resolve_target_owner_id(
    db: Session,
    item,
    project_id: int | None,
    rule: HandlerTransitionRule,
) -> int | None:
    if rule.target_type == "keep_current":
        return getattr(item, "owner_id", None)
    if rule.target_type == "none":
        return None
    if rule.target_type == "proposer":
        return getattr(item, "proposer_id", None)
    if rule.target_type == "reporter":
        return getattr(item, "reporter_id", None)
    if rule.target_type == "last_resolver":
        return _last_bug_resolver_id(db, item)
    if rule.target_type == "project_role":
        return _first_project_member_id(db, project_id, _split_csv(rule.target_roles))
    return None


def _resolve_fallback_owner_id(
    db: Session,
    project_id: int | None,
    rule: HandlerTransitionRule,
    original_owner_id: int | None,
) -> int | None:
    if rule.fallback_type == "keep_current":
        return original_owner_id
    if rule.fallback_type == "project_role":
        return _first_project_member_id(db, project_id, _split_csv(rule.fallback_roles))
    return None


def _last_bug_resolver_id(db: Session, item) -> int | None:
    if getattr(item, "resolved_by", None):
        return item.resolved_by
    object_id = getattr(item, "id", None)
    if not object_id:
        return None
    operation = (
        db.query(StatusOperationLog)
        .filter(
            StatusOperationLog.object_type == "bug",
            StatusOperationLog.object_id == object_id,
            StatusOperationLog.action == "resolve",
            StatusOperationLog.actor_id.isnot(None),
        )
        .order_by(StatusOperationLog.effective_time.desc(), StatusOperationLog.id.desc())
        .first()
    )
    return operation.actor_id if operation else None


def _first_project_member_id(db: Session, project_id: int | None, roles: list[str]) -> int | None:
    if not project_id or not roles:
        return None
    for role in roles:
        member = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id, ProjectMember.project_role == role)
            .order_by(ProjectMember.sort_order.asc(), ProjectMember.id.asc())
            .first()
        )
        if member:
            return member.user_id
    return None


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]

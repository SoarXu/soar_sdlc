from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.views.assignee_rule_config_view import AssigneeRuleConfigCreate, AssigneeRuleConfigUpdate


DEFAULT_ASSIGNEE_RULE_CONFIG = {
    "name": "默认工作流规则",
    "description": "通过工作流和处理人流转规则分派当前处理人",
    "requirement_owner_roles": "",
    "task_owner_roles": "",
    "test_case_tester_roles": "",
    "test_run_owner_roles": "",
    "bug_owner_roles": "",
    "enabled": True,
}


def ensure_default_assignee_rule_config(db: Session) -> None:
    legacy_default = db.query(AssigneeRuleConfig).filter(AssigneeRuleConfig.name == "默认责任人规则").first()
    if legacy_default:
        for field, value in DEFAULT_ASSIGNEE_RULE_CONFIG.items():
            setattr(legacy_default, field, value)
        legacy_default.update_time = datetime.now()
        db.commit()
        return
    if not db.query(AssigneeRuleConfig).first():
        db.add(AssigneeRuleConfig(**DEFAULT_ASSIGNEE_RULE_CONFIG))
        db.commit()


def list_configs(db: Session) -> list[AssigneeRuleConfig]:
    ensure_default_assignee_rule_config(db)
    return db.query(AssigneeRuleConfig).order_by(AssigneeRuleConfig.enabled.desc(), AssigneeRuleConfig.id.asc()).all()


def create_config(db: Session, payload: AssigneeRuleConfigCreate) -> AssigneeRuleConfig:
    data = _clean_payload(payload.model_dump())
    if "name" in data:
        if not data["name"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name is required")
    if db.query(AssigneeRuleConfig).filter(AssigneeRuleConfig.name == data["name"]).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Config name already exists")
    config = AssigneeRuleConfig(**data)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def update_config(db: Session, config_id: int, payload: AssigneeRuleConfigUpdate) -> AssigneeRuleConfig:
    config = _get_config(db, config_id)
    data = _clean_payload(payload.model_dump(exclude_unset=True))
    if "name" in data:
        if not data["name"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name is required")
        existing = db.query(AssigneeRuleConfig).filter(AssigneeRuleConfig.name == data["name"]).first()
        if existing and existing.id != config_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Config name already exists")
    for field, value in data.items():
        setattr(config, field, value)
    config.update_time = datetime.now()
    db.commit()
    db.refresh(config)
    return config


def delete_config(db: Session, config_id: int) -> None:
    config = _get_config(db, config_id)
    config.enabled = False
    config.update_time = datetime.now()
    db.commit()


def _get_config(db: Session, config_id: int) -> AssigneeRuleConfig:
    config = db.query(AssigneeRuleConfig).filter(AssigneeRuleConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee rule config not found")
    return config


def _clean_payload(data: dict) -> dict:
    cleaned = dict(data)
    if "name" in cleaned and cleaned["name"] is not None:
        cleaned["name"] = cleaned["name"].strip()
    for field in [
        "requirement_owner_roles",
        "task_owner_roles",
        "test_case_tester_roles",
        "test_run_owner_roles",
        "bug_owner_roles",
    ]:
        if field in cleaned and cleaned[field] is not None:
            cleaned[field] = ",".join(_split_roles(cleaned[field]))
    return cleaned


def _split_roles(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]

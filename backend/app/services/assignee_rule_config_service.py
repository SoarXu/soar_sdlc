from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.project import Project
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.views.assignee_rule_config_view import AssigneeRuleConfigCreate, AssigneeRuleConfigUpdate


DEFAULT_ASSIGNEE_RULE_CONFIG = {
    "name": "默认工作流规则",
    "description": "通过工作流和处理人流转规则分派当前处理人",
    "requirement_owner_roles": "",
    "task_owner_roles": "",
    "test_case_tester_roles": "",
    "test_run_owner_roles": "",
    "bug_owner_roles": "",
    "lifecycle_status": "enabled",
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
    return db.query(AssigneeRuleConfig).order_by(AssigneeRuleConfig.lifecycle_status.asc(), AssigneeRuleConfig.id.asc()).all()


def list_project_options(db: Session) -> list[AssigneeRuleConfig]:
    ensure_default_assignee_rule_config(db)
    return (
        db.query(AssigneeRuleConfig)
        .filter(AssigneeRuleConfig.lifecycle_status == "enabled")
        .order_by(AssigneeRuleConfig.id.asc())
        .all()
    )


def create_config(db: Session, payload: AssigneeRuleConfigCreate) -> AssigneeRuleConfig:
    data = _clean_payload(payload.model_dump())
    if "name" in data:
        if not data["name"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name is required")
    if db.query(AssigneeRuleConfig).filter(AssigneeRuleConfig.name == data["name"]).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Config name already exists")
    config = AssigneeRuleConfig(**data, lifecycle_status="draft", enabled=False)
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


def enable_config(db: Session, config_id: int) -> AssigneeRuleConfig:
    config = _get_config(db, config_id)
    if config.lifecycle_status == "disabled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Disabled workflow scheme recovery is not supported",
        )
    invalid = _invalid_core_workflows(db, config_id)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Workflow scheme is not runnable",
                "invalid_object_types": sorted(invalid),
                "errors": invalid,
            },
        )
    config.lifecycle_status = "enabled"
    config.enabled = True
    config.update_time = datetime.now()
    db.commit()
    db.refresh(config)
    return config


def disable_config(db: Session, config_id: int) -> AssigneeRuleConfig:
    config = _get_config(db, config_id)
    project_ids = [
        int(item[0])
        for item in db.query(Project.id)
        .filter(Project.assignee_rule_config_id == config_id, Project.deleted == 0)
        .order_by(Project.id.asc())
        .all()
    ]
    if project_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Workflow scheme is still assigned to projects",
                "project_count": len(project_ids),
                "project_ids": project_ids,
                "projects_url": f"/api/v1/projects?assignee_rule_config_id={config_id}",
            },
        )
    if config.lifecycle_status != "enabled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only enabled workflow schemes can be disabled",
        )
    config.lifecycle_status = "disabled"
    config.enabled = False
    config.update_time = datetime.now()
    db.commit()
    db.refresh(config)
    return config


def _invalid_core_workflows(db: Session, config_id: int) -> dict[str, str]:
    invalid: dict[str, str] = {}
    for object_type in ("requirement", "task", "bug"):
        definitions = (
            db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.scope_type == "assignee_rule_config",
                WorkflowDefinition.scope_id == config_id,
                WorkflowDefinition.object_type == object_type,
                WorkflowDefinition.enabled.is_(True),
            )
            .all()
        )
        if len(definitions) != 1:
            invalid[object_type] = "exactly one enabled definition is required"
            continue
        definition = definitions[0]
        initial_state = (
            db.query(WorkflowState)
            .filter(
                WorkflowState.id == definition.initial_state_id,
                WorkflowState.definition_id == definition.id,
                WorkflowState.enabled.is_(True),
            )
            .first()
        )
        if not initial_state:
            invalid[object_type] = "an enabled initial state is required"
            continue
        enabled_state_ids = {
            int(item[0])
            for item in db.query(WorkflowState.id)
            .filter(WorkflowState.definition_id == definition.id, WorkflowState.enabled.is_(True))
            .all()
        }
        transitions = (
            db.query(WorkflowTransition)
            .filter(WorkflowTransition.definition_id == definition.id, WorkflowTransition.enabled.is_(True))
            .all()
        )
        if not transitions:
            invalid[object_type] = "at least one enabled transition is required"
            continue
        if any(
            item.from_state_id not in enabled_state_ids or item.to_state_id not in enabled_state_ids
            for item in transitions
        ):
            invalid[object_type] = "all transitions must reference enabled states in the definition"
    return invalid


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

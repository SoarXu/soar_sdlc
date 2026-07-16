from copy import deepcopy
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.handler_transition_rule import HandlerTransitionRule
from app.models.project import Project
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.services.default_workflow_template_service import ensure_default_workflow_templates
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


def list_template_sources(db: Session) -> list[dict]:
    ensure_default_workflow_templates(db)
    sources = [
        {
            "source_type": "system",
            "source_id": "system-standard",
            "name": "系统标准方案",
            "description": "系统内置的需求、任务和 Bug 标准工作流",
            "lifecycle_status": "enabled",
        }
    ]
    sources.extend(
        {
            "source_type": "scheme",
            "source_id": str(item.id),
            "name": item.name,
            "description": item.description,
            "lifecycle_status": item.lifecycle_status,
        }
        for item in db.query(AssigneeRuleConfig).order_by(AssigneeRuleConfig.id.asc()).all()
    )
    return sources


def create_config(db: Session, payload: AssigneeRuleConfigCreate) -> AssigneeRuleConfig:
    data = _clean_payload(payload.model_dump(exclude={"creation_mode", "template_source"}))
    if "name" in data:
        if not data["name"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name is required")
    if db.query(AssigneeRuleConfig).filter(AssigneeRuleConfig.name == data["name"]).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Config name already exists")
    if payload.creation_mode == "blank" and payload.template_source is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Blank creation does not accept a template source",
        )
    if payload.creation_mode == "template" and payload.template_source is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Template source is required",
        )
    if payload.template_source and payload.template_source.source_type == "system":
        if payload.template_source.source_id != "system-standard":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System template source not found")
        ensure_default_workflow_templates(db)
    try:
        config = AssigneeRuleConfig(**data, lifecycle_status="draft", enabled=False)
        db.add(config)
        db.flush()
        for object_type, label in (("requirement", "需求"), ("task", "任务"), ("bug", "Bug")):
            db.add(
                WorkflowDefinition(
                    name=f"{config.name}-{label}工作流",
                    object_type=object_type,
                    scope_type="assignee_rule_config",
                    scope_id=config.id,
                    template_key=None,
                    parent_definition_id=None,
                    is_default_template=False,
                    enabled=True,
                    version=1,
                )
            )
        db.flush()
        if payload.creation_mode == "template":
            _copy_template_source(db, config.id, payload.template_source)
        db.commit()
        db.refresh(config)
        return config
    except Exception:
        db.rollback()
        raise


def _copy_template_source(db: Session, config_id: int, source) -> None:
    source_definitions = _source_definitions(db, source)
    target_definitions = {
        item.object_type: item
        for item in db.query(WorkflowDefinition)
        .filter(
            WorkflowDefinition.scope_type == "assignee_rule_config",
            WorkflowDefinition.scope_id == config_id,
        )
        .all()
    }
    for object_type in ("requirement", "task", "bug"):
        _clone_graph(db, source_definitions[object_type], target_definitions[object_type])

    from app.services.workflow_definition_service import _sync_handler_rules

    target_transitions = (
        db.query(WorkflowTransition)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowTransition.definition_id)
        .filter(
            WorkflowDefinition.scope_type == "assignee_rule_config",
            WorkflowDefinition.scope_id == config_id,
        )
        .all()
    )
    definitions_by_id = {item.id: item for item in target_definitions.values()}
    for definition_id, definition in definitions_by_id.items():
        _sync_handler_rules(
            db,
            definition,
            [item for item in target_transitions if item.definition_id == definition_id],
        )

    if source.source_type == "scheme":
        _clone_additional_handler_rules(db, int(source.source_id), config_id)


def _source_definitions(db: Session, source) -> dict[str, WorkflowDefinition]:
    if source.source_type == "system":
        if source.source_id != "system-standard":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System template source not found")
        query = db.query(WorkflowDefinition).filter(
            WorkflowDefinition.scope_type == "system",
            WorkflowDefinition.is_default_template.is_(True),
            WorkflowDefinition.object_type.in_(("requirement", "task", "bug")),
        )
    else:
        try:
            source_config_id = int(source.source_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid scheme source id") from exc
        source_config = db.query(AssigneeRuleConfig.id).filter(AssigneeRuleConfig.id == source_config_id).first()
        if not source_config:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow scheme source not found")
        query = db.query(WorkflowDefinition).filter(
            WorkflowDefinition.scope_type == "assignee_rule_config",
            WorkflowDefinition.scope_id == source_config_id,
            WorkflowDefinition.object_type.in_(("requirement", "task", "bug")),
            WorkflowDefinition.enabled.is_(True),
        )
    definitions: dict[str, WorkflowDefinition] = {}
    for item in query.order_by(WorkflowDefinition.id.desc()).all():
        definitions.setdefault(item.object_type, item)
    missing = {"requirement", "task", "bug"} - set(definitions)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Template source is incomplete", "missing_object_types": sorted(missing)},
        )
    return definitions


def _clone_graph(db: Session, source: WorkflowDefinition, target: WorkflowDefinition) -> None:
    source_states = (
        db.query(WorkflowState)
        .filter(WorkflowState.definition_id == source.id)
        .order_by(WorkflowState.sort_order.asc(), WorkflowState.id.asc())
        .all()
    )
    state_id_map: dict[int, int] = {}
    target_states: dict[int, WorkflowState] = {}
    for item in source_states:
        cloned = WorkflowState(
            definition_id=target.id,
            status_key=item.status_key,
            status_name=item.status_name,
            category=item.category,
            color=item.color,
            x=item.x,
            y=item.y,
            sort_order=item.sort_order,
            enabled=item.enabled,
        )
        db.add(cloned)
        db.flush()
        state_id_map[item.id] = cloned.id
        target_states[cloned.id] = cloned

    target.initial_state_id = state_id_map.get(source.initial_state_id)
    source_transitions = (
        db.query(WorkflowTransition)
        .filter(WorkflowTransition.definition_id == source.id)
        .order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc())
        .all()
    )
    for item in source_transitions:
        from_state_id = state_id_map[item.from_state_id]
        to_state_id = state_id_map[item.to_state_id]
        db.add(
            WorkflowTransition(
                definition_id=target.id,
                action_key=item.action_key,
                action_name=item.action_name,
                from_status=target_states[from_state_id].status_key,
                to_status=target_states[to_state_id].status_key,
                from_state_id=from_state_id,
                to_state_id=to_state_id,
                allowed_roles=item.allowed_roles,
                handler_rule=deepcopy(item.handler_rule),
                trigger_config=deepcopy(item.trigger_config),
                condition_config=_remap_state_ids(item.condition_config, state_id_map),
                validator_config=deepcopy(item.validator_config),
                post_action_config=deepcopy(item.post_action_config),
                ui_config=deepcopy(item.ui_config),
                form_config=deepcopy(item.form_config),
                enabled=item.enabled,
                sort_order=item.sort_order,
            )
        )
    db.flush()


def _remap_state_ids(config, state_id_map: dict[int, int]):
    if not isinstance(config, dict):
        return deepcopy(config)
    remapped = deepcopy(config)
    for field in ("routes", "target_state_id_by_owner"):
        if isinstance(remapped.get(field), dict):
            remapped[field] = {
                key: state_id_map.get(value, value)
                for key, value in remapped[field].items()
            }
    return remapped


def _clone_additional_handler_rules(db: Session, source_config_id: int, target_config_id: int) -> None:
    graph_rule_keys = {
        (definition.object_type, transition.action_key, transition.from_status, transition.to_status)
        for transition, definition in db.query(WorkflowTransition, WorkflowDefinition)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowTransition.definition_id)
        .filter(
            WorkflowDefinition.scope_type == "assignee_rule_config",
            WorkflowDefinition.scope_id == source_config_id,
        )
        .all()
    }
    source_rules = (
        db.query(HandlerTransitionRule)
        .filter(HandlerTransitionRule.config_id == source_config_id)
        .order_by(HandlerTransitionRule.id.asc())
        .all()
    )
    for item in source_rules:
        if (item.object_type, item.action, item.from_status, item.to_status) in graph_rule_keys:
            continue
        existing = (
            db.query(HandlerTransitionRule)
            .filter(
                HandlerTransitionRule.config_id == target_config_id,
                HandlerTransitionRule.rule_type == item.rule_type,
                HandlerTransitionRule.object_type == item.object_type,
                HandlerTransitionRule.action == item.action,
                HandlerTransitionRule.from_status == item.from_status,
                HandlerTransitionRule.to_status == item.to_status,
            )
            .first()
        )
        data = {
            "target_type": item.target_type,
            "target_roles": item.target_roles,
            "fallback_type": item.fallback_type,
            "fallback_roles": item.fallback_roles,
            "enabled": item.enabled,
        }
        if existing:
            for field, value in data.items():
                setattr(existing, field, value)
        else:
            db.add(
                HandlerTransitionRule(
                    config_id=target_config_id,
                    rule_type=item.rule_type,
                    object_type=item.object_type,
                    action=item.action,
                    from_status=item.from_status,
                    to_status=item.to_status,
                    **data,
                )
            )
    db.flush()


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

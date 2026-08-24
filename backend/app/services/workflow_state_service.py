from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.business_component import BusinessComponent
from app.models.iteration import Iteration
from app.models.project import Project
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.services.default_workflow_template_service import ensure_default_workflow_templates


CORE_OBJECT_TYPES = {"requirement", "task", "bug", "project"}
SYSTEM_OBJECT_TYPES = {"project", "iteration"}
WORK_ITEM_OBJECT_TYPES = {"requirement", "task", "bug"}
WORK_ITEM_STATE_ROLES = {"unassigned", "waiting_iteration", "active_work"}


def initial_workflow_values(
    db: Session,
    object_type: str,
    project_id: int | None,
    primary_component_id: int | None = None,
) -> dict:
    definition, initial_state = resolve_effective_workflow(db, object_type, project_id, primary_component_id)
    return {
        "workflow_definition_id": definition.id,
        "current_state_id": initial_state.id,
    }


def initial_work_item_workflow_values(
    db: Session,
    object_type: str,
    project_id: int | None,
    owner_id: int | None,
    iteration_id: int | None,
    primary_component_id: int | None = None,
) -> dict:
    if object_type not in WORK_ITEM_OBJECT_TYPES:
        return initial_workflow_values(db, object_type, project_id, primary_component_id)
    definition, _initial_state = resolve_effective_workflow(db, object_type, project_id, primary_component_id)
    state_role = "unassigned" if owner_id is None else (
        "active_work" if _iteration_is_active(db, iteration_id) else "waiting_iteration"
    )
    state = state_for_role(db, definition.id, state_role)
    return {
        "workflow_definition_id": definition.id,
        "current_state_id": state.id,
    }


def state_for_role(db: Session, definition_id: int, state_role: str) -> WorkflowState:
    if state_role not in WORK_ITEM_STATE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "WORKFLOW_STATE_ROLE_INVALID",
                "message": f"Unsupported work-item state role: {state_role}",
            },
        )
    states = (
        db.query(WorkflowState)
        .filter(
            WorkflowState.definition_id == definition_id,
            WorkflowState.state_role == state_role,
            WorkflowState.enabled.is_(True),
        )
        .order_by(WorkflowState.id.asc())
        .all()
    )
    if len(states) != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "WORKFLOW_STATE_ROLE_CONFIGURATION_INVALID",
                "message": f"Workflow definition {definition_id} must configure one enabled {state_role} state",
                "definition_id": definition_id,
                "state_role": state_role,
            },
        )
    return states[0]


def _iteration_is_active(db: Session, iteration_id: int | None) -> bool:
    if iteration_id is None:
        return False
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    if not iteration:
        return False
    return bool(
        db.query(WorkflowTransition.id)
        .filter(
            WorkflowTransition.definition_id == iteration.workflow_definition_id,
            WorkflowTransition.from_state_id == iteration.current_state_id,
            WorkflowTransition.action_key.in_(("complete", "cancel")),
            WorkflowTransition.enabled.is_(True),
        )
        .first()
    )


def initial_system_workflow_values(db: Session, object_type: str) -> dict:
    if object_type not in SYSTEM_OBJECT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported system workflow object type")
    ensure_default_workflow_templates(db)
    definition_query = (
        db.query(WorkflowDefinition)
        .filter(
            WorkflowDefinition.object_type == object_type,
            WorkflowDefinition.scope_type == "system",
            WorkflowDefinition.is_default_template.is_(True),
            WorkflowDefinition.enabled.is_(True),
        )
        .order_by(WorkflowDefinition.id.desc())
    )
    definition = definition_query.first()
    if not definition:
        ensure_default_workflow_templates(db)
        definition = definition_query.first()
    if not definition:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="System workflow definition not found")
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow definition {definition.id} has no valid initial state",
        )
    return {"workflow_definition_id": definition.id, "current_state_id": initial_state.id}


def resolve_effective_workflow(
    db: Session,
    object_type: str,
    project_id: int | None,
    primary_component_id: int | None = None,
) -> tuple[WorkflowDefinition, WorkflowState]:
    if object_type not in CORE_OBJECT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported workflow object type")
    if not project_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Project is required for workflow")
    ensure_default_workflow_templates(db)
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    component_scheme_id = None
    if primary_component_id is not None:
        component = (
            db.query(BusinessComponent)
            .filter(
                BusinessComponent.id == primary_component_id,
                BusinessComponent.project_id == project.id,
                BusinessComponent.enabled.is_(True),
            )
            .first()
        )
        if not component:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid primary business component")
        component_scheme_id = component.workflow_scheme_id

    scheme_id = component_scheme_id or project.assignee_rule_config_id
    if scheme_id:
        config = (
            db.query(AssigneeRuleConfig)
            .filter(AssigneeRuleConfig.id == scheme_id)
            .first()
        )
        if not config or config.lifecycle_status != "enabled":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project workflow scheme is not enabled",
            )
        definitions = (
            db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.object_type == object_type,
                WorkflowDefinition.scope_type == "assignee_rule_config",
                WorkflowDefinition.scope_id == config.id,
                WorkflowDefinition.enabled.is_(True),
            )
            .order_by(WorkflowDefinition.id.asc())
            .all()
        )
        if len(definitions) != 1:
            object_label = {"requirement": "需求", "task": "任务", "bug": "Bug", "project": "项目"}[object_type]
            if definitions:
                conflicts = "、".join(f"ID {item.id}（{item.name}）" for item in definitions)
                detail = (
                    f"项目 {project.id} 绑定的工作流方案 {config.id} 存在多个启用的 {object_label} 工作流定义："
                    f"{conflicts}；请停用多余定义后重试。"
                )
            else:
                detail = f"项目 {project.id} 绑定的工作流方案 {config.id} 没有启用的 {object_label} 工作流定义。"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            )
        definition = definitions[0]
    else:
        definition_query = (
            db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.object_type == object_type,
                WorkflowDefinition.scope_type == "system",
                WorkflowDefinition.is_default_template.is_(True),
                WorkflowDefinition.enabled.is_(True),
            )
            .order_by(WorkflowDefinition.id.desc())
        )
        definition = definition_query.first()
        if not definition:
            ensure_default_workflow_templates(db)
            definition = definition_query.first()
        if not definition:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="System workflow definition not found")

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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow definition {definition.id} has no valid initial state",
        )
    return definition, initial_state

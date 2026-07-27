from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.business_component import BusinessComponent
from app.models.project import Project
from app.models.workflow_definition import WorkflowDefinition, WorkflowState
from app.services.default_workflow_template_service import ensure_default_workflow_templates


CORE_OBJECT_TYPES = {"requirement", "task", "bug"}
SYSTEM_OBJECT_TYPES = {"project", "iteration"}


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


def initial_system_workflow_values(db: Session, object_type: str) -> dict:
    if object_type not in SYSTEM_OBJECT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported system workflow object type")
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
            object_label = {"requirement": "需求", "task": "任务", "bug": "Bug"}[object_type]
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

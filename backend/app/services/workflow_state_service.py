from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.project import Project
from app.models.workflow_definition import WorkflowDefinition, WorkflowState
from app.services.default_workflow_template_service import ensure_default_workflow_templates


CORE_OBJECT_TYPES = {"requirement", "task", "bug"}


def initial_workflow_values(db: Session, object_type: str, project_id: int | None) -> dict:
    definition, initial_state = resolve_effective_workflow(db, object_type, project_id)
    return {
        "workflow_definition_id": definition.id,
        "current_state_id": initial_state.id,
        "status": initial_state.status_key,
    }


def resolve_effective_workflow(
    db: Session,
    object_type: str,
    project_id: int | None,
) -> tuple[WorkflowDefinition, WorkflowState]:
    if object_type not in CORE_OBJECT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported workflow object type")
    if not project_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Project is required for workflow")
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if project.assignee_rule_config_id:
        config = (
            db.query(AssigneeRuleConfig)
            .filter(AssigneeRuleConfig.id == project.assignee_rule_config_id)
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
            .all()
        )
        if len(definitions) != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project workflow scheme has no unique {object_type} definition",
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

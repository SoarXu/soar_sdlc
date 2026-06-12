from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.workflow_component import WorkflowComponent
from app.services.workflow_catalog import DEFAULT_WORKFLOW_COMPONENTS, WORKFLOW_HANDLERS, handler_keys
from app.views.workflow_component_view import WorkflowComponentCreate, WorkflowComponentUpdate


VALID_COMPONENT_TYPES = {"trigger", "condition", "action"}


def ensure_default_workflow_components(db: Session) -> None:
    existing_keys = {
        row.component_key
        for row in db.query(WorkflowComponent.component_key)
        .filter(WorkflowComponent.component_key.in_([item["component_key"] for item in DEFAULT_WORKFLOW_COMPONENTS]))
        .all()
    }
    missing = [item for item in DEFAULT_WORKFLOW_COMPONENTS if item["component_key"] not in existing_keys]
    if not missing:
        return
    db.add_all(WorkflowComponent(**item) for item in missing)
    db.commit()


def list_workflow_handlers() -> list[dict]:
    return WORKFLOW_HANDLERS


def list_components(db: Session, include_disabled: bool = True) -> list[WorkflowComponent]:
    ensure_default_workflow_components(db)
    query = db.query(WorkflowComponent)
    if not include_disabled:
        query = query.filter(WorkflowComponent.enabled == True)  # noqa: E712
    return query.order_by(WorkflowComponent.component_type.asc(), WorkflowComponent.sort_order.asc(), WorkflowComponent.id.asc()).all()


def list_designer_components(db: Session) -> list[dict]:
    return [_to_designer_component(component) for component in list_components(db, include_disabled=False)]


def create_component(db: Session, payload: WorkflowComponentCreate) -> WorkflowComponent:
    data = payload.model_dump()
    _validate_component_data(data)
    component = WorkflowComponent(**data)
    db.add(component)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="组件标识已存在") from exc
    db.refresh(component)
    return component


def update_component(db: Session, component_id: int, payload: WorkflowComponentUpdate) -> WorkflowComponent:
    component = _get_component(db, component_id)
    data = payload.model_dump(exclude_unset=True)
    merged = {
        "component_key": component.component_key,
        "component_type": component.component_type,
        "handler_key": component.handler_key,
        **data,
    }
    _validate_component_data(merged)
    for field, value in data.items():
        setattr(component, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="组件标识已存在") from exc
    db.refresh(component)
    return component


def delete_component(db: Session, component_id: int) -> None:
    component = _get_component(db, component_id)
    if component.is_system:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="系统内置组件不允许删除")
    db.delete(component)
    db.commit()


def _get_component(db: Session, component_id: int) -> WorkflowComponent:
    component = db.query(WorkflowComponent).filter(WorkflowComponent.id == component_id).first()
    if not component:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow component not found")
    return component


def _validate_component_data(data: dict) -> None:
    if data.get("component_type") not in VALID_COMPONENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未知的组件类型")
    if data.get("handler_key") not in handler_keys():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未知的工作流 handler")


def _to_designer_component(component: WorkflowComponent) -> dict:
    return {
        "component_key": component.component_key,
        "category": component.component_type,
        "label": component.component_name,
        "description": component.description or "",
        "handler_key": component.handler_key,
        "object_type": component.object_type,
        "config_schema": component.config_schema or [],
    }

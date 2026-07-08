from typing import Any

from pydantic import BaseModel, Field


class WorkflowTransitionActionRead(BaseModel):
    action_key: str
    action_name: str
    from_status: str
    to_status: str
    button_type: str = "primary"
    list_display: str = "more"
    list_priority: int = 100
    requires_form: bool = False
    confirm_required: bool = False
    ui_config: dict[str, Any] = Field(default_factory=dict)
    form_config: dict[str, Any] = Field(default_factory=dict)


class WorkflowTransitionExecuteRequest(BaseModel):
    action_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    next_owner_id: int | None = None
    delegate_reason: str | None = None


class WorkflowTransitionBatchItem(BaseModel):
    object_type: str
    id: int


class WorkflowTransitionBatchRequest(BaseModel):
    items: list[WorkflowTransitionBatchItem]


class WorkflowTransitionBatchResultItem(BaseModel):
    object_type: str
    id: int
    transitions: list[WorkflowTransitionActionRead] = Field(default_factory=list)


class WorkflowTransitionBatchRead(BaseModel):
    items: list[WorkflowTransitionBatchResultItem] = Field(default_factory=list)


class WorkflowTransitionExecuteRead(BaseModel):
    object_type: str
    id: int
    status: str
    owner_id: int | None = None

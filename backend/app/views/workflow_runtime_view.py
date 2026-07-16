from typing import Any

from pydantic import BaseModel, Field


class WorkflowTargetStateRead(BaseModel):
    id: int
    status_name: str


class WorkflowTransitionActionRead(BaseModel):
    action_key: str
    action_name: str
    from_state_id: int
    to_state_id: int
    button_type: str = "primary"
    list_display: str = "more"
    list_priority: int = 100
    requires_form: bool = False
    confirm_required: bool = False
    routing_mode: str | None = None
    allowed_target_state_ids: list[int] = Field(default_factory=list)
    allowed_target_states: list[WorkflowTargetStateRead] = Field(default_factory=list)
    ui_config: dict[str, Any] = Field(default_factory=dict)
    form_config: dict[str, Any] = Field(default_factory=dict)


class WorkflowTransitionExecuteRequest(BaseModel):
    action_key: str
    payload: dict[str, Any] = Field(default_factory=dict)
    next_owner_id: int | None = None
    delegate_reason: str | None = None
    selected_values: dict[str, Any] = Field(default_factory=dict)
    selected_target_status: str | None = None
    selected_target_state_id: int | None = None
    override_reason: str | None = None


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
    workflow_definition_id: int | None = None
    current_state_id: int | None = None
    status_name: str | None = None
    state_category: str | None = None
    owner_id: int | None = None
    default_target_status: str | None = None
    resolved_target_status: str | None = None
    default_target_state_id: int | None = None
    resolved_target_state_id: int | None = None
    selected_values: dict[str, Any] = Field(default_factory=dict)
    override_reason: str | None = None

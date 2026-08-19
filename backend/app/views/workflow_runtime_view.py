from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkflowTargetStateRead(BaseModel):
    id: int
    status_name: str


class WorkflowBulkAssignmentMetadata(BaseModel):
    supported: bool = False
    requires_delegate_reason: bool = False
    eligible_assignee_ids: list[int] = Field(default_factory=list)


class WorkflowTransitionActionRead(BaseModel):
    transition_id: int
    action_key: str
    action_name: str
    from_state_id: int
    to_state_id: int
    button_type: str = "primary"
    list_display: str = "more"
    sort_order: int = 100
    requires_form: bool = False
    confirm_required: bool = False
    routing_mode: str | None = None
    allowed_target_state_ids: list[int] = Field(default_factory=list)
    allowed_target_states: list[WorkflowTargetStateRead] = Field(default_factory=list)
    ui_config: dict[str, Any] = Field(default_factory=dict)
    form_config: dict[str, Any] = Field(default_factory=dict)
    eligible_assignee_ids: list[int] = Field(default_factory=list)
    bulk_assignment: WorkflowBulkAssignmentMetadata = Field(default_factory=WorkflowBulkAssignmentMetadata)


class WorkflowTransitionExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transition_id: int
    payload: dict[str, Any] = Field(default_factory=dict)
    next_owner_id: int | None = None
    delegate_reason: str | None = None
    selected_values: dict[str, Any] = Field(default_factory=dict)
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


class WorkflowBulkAssignmentItem(BaseModel):
    id: int
    transition_id: int


class WorkflowBulkAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_type: str
    project_id: int
    next_owner_id: int
    delegate_reason: str | None = None
    items: list[WorkflowBulkAssignmentItem] = Field(min_length=1)


class WorkflowBulkAssignmentRead(BaseModel):
    object_type: str
    project_id: int
    next_owner_id: int
    completed_count: int
    completed_item_ids: list[int] = Field(default_factory=list)


class WorkflowTransitionExecuteRead(BaseModel):
    object_type: str
    id: int
    workflow_definition_id: int
    current_state_id: int
    status_name: str
    state_category: str
    owner_id: int | None = None
    default_target_status: str | None = None
    resolved_target_status: str | None = None
    default_target_state_id: int | None = None
    resolved_target_state_id: int | None = None
    selected_values: dict[str, Any] = Field(default_factory=dict)
    override_reason: str | None = None
    operation_log_id: int | None = None
    audit_trail: dict[str, Any] | None = None

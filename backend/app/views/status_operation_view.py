from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StatusOperationCreate(BaseModel):
    effective_time: datetime | None = None
    reason: str | None = None
    remark: str | None = None
    target_iteration_id: int | None = None
    delegate_reason: str | None = None
    selected_values: dict | None = None
    default_target_status: str | None = None
    resolved_target_status: str | None = None
    override_reason: str | None = None
    next_owner_id: int | None = None
    next_owner_name: str | None = None
    blocker_messages: list[str] | None = None


class StatusOperationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_type: str
    object_id: int
    action: str
    workflow_definition_id: int | None = None
    from_state_id: int | None = None
    to_state_id: int | None = None
    from_state_name: str | None = None
    to_state_name: str | None = None
    from_status: str | None = None
    to_status: str
    reason: str | None = None
    effective_time: datetime
    remark: str | None = None
    actor_id: int | None = None
    actor_name: str | None = None
    is_delegated: bool = False
    delegated_owner_id: int | None = None
    delegated_owner_name: str | None = None
    delegate_reason: str | None = None
    selected_values: dict | list | None = None
    default_target_status: str | None = None
    resolved_target_status: str | None = None
    override_reason: str | None = None
    next_owner_id: int | None = None
    next_owner_name: str | None = None
    blocker_messages: dict | list | None = None
    create_time: datetime | None = None

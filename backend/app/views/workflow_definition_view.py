from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkflowDefinitionBase(BaseModel):
    name: str
    object_type: str
    scope_type: str = "system"
    scope_id: int | None = None
    enabled: bool = True


class WorkflowDefinitionCreate(WorkflowDefinitionBase):
    pass


class WorkflowDefinitionUpdate(BaseModel):
    name: str | None = None
    object_type: str | None = None
    scope_type: str | None = None
    scope_id: int | None = None
    enabled: bool | None = None


class WorkflowDefinitionRead(WorkflowDefinitionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int = 1
    create_time: datetime | None = None
    update_time: datetime | None = None


class WorkflowStateBase(BaseModel):
    status_key: str
    status_name: str
    category: str = "normal"
    color: str = "#2563eb"
    x: int = 0
    y: int = 0
    sort_order: int = 100
    enabled: bool = True


class WorkflowStateRead(WorkflowStateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    definition_id: int | None = None


class WorkflowTransitionBase(BaseModel):
    action_key: str
    action_name: str
    from_status: str
    to_status: str
    allowed_roles: str = ""
    handler_rule: dict[str, Any] | None = None
    trigger_config: dict[str, Any] | list[Any] | None = None
    condition_config: dict[str, Any] | list[Any] | None = None
    validator_config: dict[str, Any] | list[Any] | None = None
    post_action_config: dict[str, Any] | list[Any] | None = None
    ui_config: dict[str, Any] | None = None
    form_config: dict[str, Any] | None = None
    enabled: bool = True
    sort_order: int = 100


class WorkflowTransitionRead(WorkflowTransitionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    definition_id: int | None = None


class WorkflowGraphSave(BaseModel):
    states: list[WorkflowStateBase] = Field(default_factory=list)
    transitions: list[WorkflowTransitionBase] = Field(default_factory=list)


class WorkflowGraphRead(BaseModel):
    definition: WorkflowDefinitionRead
    states: list[WorkflowStateRead] = Field(default_factory=list)
    transitions: list[WorkflowTransitionRead] = Field(default_factory=list)

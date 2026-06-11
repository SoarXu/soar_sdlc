from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class WorkflowRuleBase(BaseModel):
    rule_name: str
    scope_type: str = "system"
    scope_id: int | None = None
    target_object: str
    trigger_action: str
    condition_json: dict[str, Any] | list[Any] | None = None
    action_json: dict[str, Any] | list[Any]
    enabled: bool = True
    priority: int = 100
    block_message: str | None = None
    description: str | None = None
    creator_id: int | None = None
    updater_id: int | None = None


class WorkflowRuleCreate(WorkflowRuleBase):
    pass


class WorkflowRuleUpdate(BaseModel):
    rule_name: str | None = None
    scope_type: str | None = None
    scope_id: int | None = None
    target_object: str | None = None
    trigger_action: str | None = None
    condition_json: dict[str, Any] | list[Any] | None = None
    action_json: dict[str, Any] | list[Any] | None = None
    enabled: bool | None = None
    priority: int | None = None
    block_message: str | None = None
    description: str | None = None
    updater_id: int | None = None


class WorkflowRuleRead(WorkflowRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    create_time: datetime | None = None
    update_time: datetime | None = None


class WorkflowComponentRead(BaseModel):
    component_key: str
    category: str
    label: str
    description: str
    config_schema: list[dict[str, Any]]


class WorkflowTemplateRead(BaseModel):
    template_key: str
    template_name: str
    target_object: str
    trigger_action: str
    description: str
    condition_json: dict[str, Any]
    action_json: dict[str, Any]

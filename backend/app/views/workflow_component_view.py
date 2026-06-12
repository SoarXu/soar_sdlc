from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class WorkflowComponentBase(BaseModel):
    component_key: str
    component_type: str
    component_name: str
    description: str | None = None
    object_type: str | None = None
    handler_key: str
    config_schema: list[dict[str, Any]] | dict[str, Any] | None = None
    enabled: bool = True
    is_system: bool = False
    sort_order: int = 100


class WorkflowComponentCreate(WorkflowComponentBase):
    pass


class WorkflowComponentUpdate(BaseModel):
    component_key: str | None = None
    component_type: str | None = None
    component_name: str | None = None
    description: str | None = None
    object_type: str | None = None
    handler_key: str | None = None
    config_schema: list[dict[str, Any]] | dict[str, Any] | None = None
    enabled: bool | None = None
    is_system: bool | None = None
    sort_order: int | None = None


class WorkflowComponentRead(WorkflowComponentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    create_time: datetime | None = None
    update_time: datetime | None = None


class WorkflowHandlerRead(BaseModel):
    handler_key: str
    handler_type: str
    label: str
    description: str

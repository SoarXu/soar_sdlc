from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HandlerTransitionRuleBase(BaseModel):
    config_id: int
    rule_type: str = "advanced"
    object_type: str
    action: str
    from_status: str | None = None
    to_status: str | None = None
    target_type: str = "keep_current"
    target_roles: str = ""
    fallback_type: str = "keep_current"
    fallback_roles: str = ""
    enabled: bool = True


class HandlerTransitionRuleCreate(HandlerTransitionRuleBase):
    pass


class HandlerTransitionRuleUpdate(BaseModel):
    config_id: int | None = None
    rule_type: str | None = None
    object_type: str | None = None
    action: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    target_type: str | None = None
    target_roles: str | None = None
    fallback_type: str | None = None
    fallback_roles: str | None = None
    enabled: bool | None = None


class HandlerTransitionRuleRead(HandlerTransitionRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    create_time: datetime | None = None
    update_time: datetime | None = None

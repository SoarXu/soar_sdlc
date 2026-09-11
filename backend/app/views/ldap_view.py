from datetime import datetime
import ipaddress
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class LdapConfigWrite(BaseModel):
    enabled: bool = False
    protocol: Literal["ldap", "ldaps"] = "ldaps"
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    connect_timeout: int = Field(default=5, ge=1, le=30)
    base_dn: str = Field(min_length=1, max_length=512)
    bind_username: str = Field(min_length=1, max_length=512)
    bind_password: str | None = None
    user_base_dn: str | None = Field(default=None, max_length=512)
    user_filter: str = Field(min_length=1, max_length=1000)
    exclude_disabled: bool = True
    page_size: int = Field(default=50, ge=1, le=200)
    username_attribute: str = "sAMAccountName"
    employee_no_attribute: str = "employeeID"
    full_name_attribute: str = "displayName"
    email_attribute: str = "mail"
    mobile_attribute: str = "mobile"
    department_attribute: str = "department"
    external_id_attribute: str = "objectGUID"

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        value = value.strip()
        try:
            ipaddress.ip_address(value)
            return value
        except ValueError:
            pass
        if len(value) > 253 or not re.fullmatch(
            r"(?=.{1,253}\Z)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
            r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?",
            value,
        ):
            raise ValueError("LDAP 服务器地址必须是主机名或 IP 地址")
        return value

    @field_validator(
        "host", "base_dn", "bind_username", "user_filter", "username_attribute",
        "employee_no_attribute", "full_name_attribute", "email_attribute",
        "mobile_attribute", "department_attribute", "external_id_attribute",
    )
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("字段不能为空")
        return value

    @field_validator(
        "username_attribute", "employee_no_attribute", "full_name_attribute",
        "email_attribute", "mobile_attribute", "department_attribute", "external_id_attribute",
    )
    @classmethod
    def validate_attribute_name(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", value):
            raise ValueError("LDAP 属性名格式不正确")
        return value


class LdapConfigRead(BaseModel):
    enabled: bool
    protocol: str
    host: str
    port: int
    connect_timeout: int
    base_dn: str
    bind_username: str
    has_bind_password: bool
    user_base_dn: str | None
    user_filter: str
    exclude_disabled: bool
    page_size: int
    username_attribute: str
    employee_no_attribute: str
    full_name_attribute: str
    email_attribute: str
    mobile_attribute: str
    department_attribute: str
    external_id_attribute: str
    tested_at: datetime | None
    configuration_tested: bool


class LdapDirectoryUser(BaseModel):
    username: str | None
    employee_no: str | None
    full_name: str | None
    email: str | None
    mobile: str | None
    department: str | None
    external_id: str | None
    dn: str | None
    enabled: bool
    sync_status: Literal["unlinked", "match_suggested", "linked", "conflict", "ad_disabled"]
    matched_user: "LdapMatchedUser | None" = None
    conflict_reason: str | None = None


class LdapMatchedUser(BaseModel):
    id: int
    username: str
    full_name: str
    employee_no: str | None
    auth_source: str


class LdapDirectoryPage(BaseModel):
    items: list[LdapDirectoryUser]
    page_size: int
    next_cursor: str | None
    total: int | None = None


class LdapTestResult(BaseModel):
    success: bool
    message: str
    sampled_users: int
    tested_at: datetime


class LdapSyncSelection(BaseModel):
    external_id: str = Field(min_length=1, max_length=255)
    decision: Literal["create", "bind", "update"]
    user_id: int | None = Field(default=None, ge=1)

    @field_validator("external_id")
    @classmethod
    def strip_external_id(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_decision_target(self):
        if self.decision == "bind" and self.user_id is None:
            raise ValueError("绑定现有用户时必须提供 user_id")
        if self.decision != "bind" and self.user_id is not None:
            raise ValueError("仅绑定决策允许提供 user_id")
        return self


class LdapSyncRequest(BaseModel):
    items: list[LdapSyncSelection] = Field(max_length=200)


class LdapSyncItemResult(BaseModel):
    external_id: str
    status: Literal["created", "bound", "updated", "skipped", "failed"]
    user_id: int | None = None
    code: str | None = None
    message: str | None = None


class LdapSyncSummary(BaseModel):
    total: int
    created: int
    bound: int
    updated: int
    skipped: int
    failed: int


class LdapSyncResponse(BaseModel):
    run_id: int
    summary: LdapSyncSummary
    items: list[LdapSyncItemResult]


class LdapSyncRunRead(BaseModel):
    id: int
    initiated_by_user_id: int | None
    status: Literal["running", "completed", "partial_failed", "failed"]
    total_count: int
    created_count: int
    bound_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    started_at: datetime
    completed_at: datetime | None
    error_summary: str | None = None


class LdapSyncRunPage(BaseModel):
    items: list[LdapSyncRunRead]
    total: int
    page: int
    page_size: int

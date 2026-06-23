from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DevopsRepositoryBase(BaseModel):
    provider: str = "gitlab"
    name: str
    repository_url: str | None = None
    external_project_id: str | None = None
    default_branch: str | None = None
    access_token_encrypted: str | None = None
    enabled: int = 1


class DevopsRepositoryCreate(DevopsRepositoryBase):
    pass


class DevopsRepositoryUpdate(BaseModel):
    provider: str | None = None
    name: str | None = None
    repository_url: str | None = None
    external_project_id: str | None = None
    default_branch: str | None = None
    access_token_encrypted: str | None = None
    enabled: int | None = None


class DevopsRepositoryRead(DevopsRepositoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    create_time: datetime | None = None
    update_time: datetime | None = None


class DevopsJenkinsJobBase(BaseModel):
    job_name: str
    jenkins_url: str | None = None
    repository_id: int | None = None
    branch_pattern: str | None = None
    enabled: int = 1


class DevopsJenkinsJobCreate(DevopsJenkinsJobBase):
    pass


class DevopsJenkinsJobUpdate(BaseModel):
    job_name: str | None = None
    jenkins_url: str | None = None
    repository_id: int | None = None
    branch_pattern: str | None = None
    enabled: int | None = None


class DevopsJenkinsJobRead(DevopsJenkinsJobBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    create_time: datetime | None = None
    update_time: datetime | None = None


class DevopsCommitIngest(BaseModel):
    provider: str = "gitlab"
    repository_id: int | None = None
    external_project_id: str | None = None
    commit_sha: str
    short_sha: str | None = None
    branch_name: str | None = None
    title: str | None = None
    message: str | None = None
    author_name: str | None = None
    author_email: str | None = None
    committed_at: datetime | None = None
    web_url: str | None = None
    diff_text: str | None = None
    diff_json: Any | None = None
    raw_payload: Any | None = None


class GitlabWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")


class DevopsCommitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    repository_id: int | None = None
    external_project_id: str | None = None
    commit_sha: str
    short_sha: str | None = None
    branch_name: str | None = None
    title: str | None = None
    message: str | None = None
    author_name: str | None = None
    author_email: str | None = None
    committed_at: datetime | None = None
    web_url: str | None = None
    review_status: str
    reviewer_id: int | None = None
    review_time: datetime | None = None
    review_remark: str | None = None
    create_time: datetime | None = None


class DevopsCommitDetail(DevopsCommitRead):
    diff_text: str | None = None
    diff_json: Any | None = None
    links: list[dict[str, Any]] = []


class DevopsReviewTaskRead(BaseModel):
    id: int
    commit_id: int
    title: str
    owner_id: int | None = None
    status: str
    create_time: datetime | None = None
    finish_time: datetime | None = None
    commit: DevopsCommitRead | None = None
    links: list[dict[str, Any]] = []


class DevopsReviewRequest(BaseModel):
    reviewer_id: int | None = None
    remark: str | None = None

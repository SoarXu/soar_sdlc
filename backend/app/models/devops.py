from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DevopsRepository(Base):
    __tablename__ = "devops_repositories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), default="gitlab")
    name: Mapped[str] = mapped_column(String(150))
    repository_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    external_project_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    default_branch: Mapped[str | None] = mapped_column(String(128), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
    deleted: Mapped[int] = mapped_column(Integer, default=0)
    delete_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DevopsJenkinsJob(Base):
    __tablename__ = "devops_jenkins_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    job_name: Mapped[str] = mapped_column(String(150))
    jenkins_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    repository_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    branch_pattern: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
    deleted: Mapped[int] = mapped_column(Integer, default=0)
    delete_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DevopsCommit(Base):
    __tablename__ = "devops_commits"
    __table_args__ = (UniqueConstraint("provider", "repository_id", "commit_sha", name="uk_devops_commit_repo_sha"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), default="gitlab")
    repository_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    external_project_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    commit_sha: Mapped[str] = mapped_column(String(128))
    short_sha: Mapped[str | None] = mapped_column(String(32), nullable=True)
    branch_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    author_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    web_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    diff_text: Mapped[str | None] = mapped_column(Text().with_variant(MEDIUMTEXT, "mysql"), nullable=True)
    diff_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    raw_payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    reviewer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    review_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
    deleted: Mapped[int] = mapped_column(Integer, default=0)
    delete_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DevopsCommitLink(Base):
    __tablename__ = "devops_commit_links"
    __table_args__ = (UniqueConstraint("commit_id", "object_type", "object_id", name="uk_devops_commit_link"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commit_id: Mapped[int] = mapped_column(BigInteger)
    object_type: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[int] = mapped_column(BigInteger)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class DevopsCodeReviewTask(Base):
    __tablename__ = "devops_code_review_tasks"
    __table_args__ = (UniqueConstraint("commit_id", name="uk_devops_review_commit"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    commit_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(500))
    owner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
    finish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DevopsJenkinsBuild(Base):
    __tablename__ = "devops_jenkins_builds"
    __table_args__ = (UniqueConstraint("job_id", "build_number", name="uk_devops_jenkins_build"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    job_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    job_name: Mapped[str] = mapped_column(String(150))
    build_number: Mapped[str] = mapped_column(String(64))
    build_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    branch_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(128), nullable=True)
    commit_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    trigger_user: Mapped[str | None] = mapped_column(String(150), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

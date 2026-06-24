from datetime import datetime
import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.devops import (
    DevopsCodeReviewTask,
    DevopsCommit,
    DevopsCommitLink,
    DevopsJenkinsBuild,
    DevopsJenkinsJob,
    DevopsRepository,
)
from app.models.requirement import Requirement
from app.models.role import Role, UserRole
from app.models.task import Task
from app.models.user import User
from app.views.devops_view import (
    DevopsCommitIngest,
    DevopsJenkinsBuildCreate,
    DevopsJenkinsJobCreate,
    DevopsJenkinsJobUpdate,
    DevopsRepositoryCreate,
    DevopsRepositoryUpdate,
    DevopsReviewRequest,
)

REFERENCE_PATTERNS = (
    ("requirement", re.compile(r"(?:REQ|REQUIREMENT)[-#:]?(\d+)", re.IGNORECASE)),
    ("task", re.compile(r"(?:TASK)[-#:]?(\d+)", re.IGNORECASE)),
    ("bug", re.compile(r"(?:BUG)[-#:]?(\d+)", re.IGNORECASE)),
)


def list_repositories(db: Session) -> list[DevopsRepository]:
    return db.query(DevopsRepository).filter(DevopsRepository.deleted == 0).order_by(DevopsRepository.id.desc()).all()


def create_repository(db: Session, payload: DevopsRepositoryCreate) -> DevopsRepository:
    repo = DevopsRepository(**payload.model_dump())
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


def update_repository(db: Session, repository_id: int, payload: DevopsRepositoryUpdate) -> DevopsRepository:
    repo = _get_repository(db, repository_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(repo, field, value)
    db.commit()
    db.refresh(repo)
    return repo


def delete_repository(db: Session, repository_id: int) -> None:
    repo = _get_repository(db, repository_id)
    repo.deleted = 1
    repo.delete_time = datetime.now()
    db.commit()


def list_jenkins_jobs(db: Session) -> list[DevopsJenkinsJob]:
    return db.query(DevopsJenkinsJob).filter(DevopsJenkinsJob.deleted == 0).order_by(DevopsJenkinsJob.id.desc()).all()


def list_jenkins_builds(db: Session, job_id: int | None = None, commit_sha: str | None = None) -> list[DevopsJenkinsBuild]:
    query = db.query(DevopsJenkinsBuild)
    if job_id:
        query = query.filter(DevopsJenkinsBuild.job_id == job_id)
    if commit_sha:
        query = query.filter(DevopsJenkinsBuild.commit_sha == commit_sha)
    return query.order_by(DevopsJenkinsBuild.id.desc()).limit(200).all()


def create_jenkins_build(db: Session, payload: DevopsJenkinsBuildCreate) -> DevopsJenkinsBuild:
    data = payload.model_dump()
    data["commit_id"] = _commit_id_for_sha(db, data.get("commit_sha"))
    build = (
        db.query(DevopsJenkinsBuild)
        .filter(
            DevopsJenkinsBuild.job_id == data.get("job_id"),
            DevopsJenkinsBuild.build_number == data["build_number"],
        )
        .first()
    )
    if build:
        for field, value in data.items():
            setattr(build, field, value)
    else:
        build = DevopsJenkinsBuild(**data)
        db.add(build)
    db.commit()
    db.refresh(build)
    return build


def ingest_jenkins_webhook(db: Session, payload: dict[str, Any]) -> DevopsJenkinsBuild:
    job_name = (
        payload.get("job_name")
        or payload.get("name")
        or payload.get("job", {}).get("name")
        or payload.get("full_project_name")
        or "Jenkins Job"
    )
    build_number = str(
        payload.get("build_number")
        or payload.get("number")
        or payload.get("build", {}).get("number")
        or payload.get("build", {}).get("full_url")
        or datetime.now().timestamp()
    )
    job = _find_jenkins_job_by_name(db, job_name)
    status_value = payload.get("status") or payload.get("result") or payload.get("build", {}).get("status") or "running"
    commit_sha = (
        payload.get("commit_sha")
        or payload.get("sha")
        or payload.get("git_commit")
        or payload.get("build", {}).get("commit_sha")
    )
    return create_jenkins_build(
        db,
        DevopsJenkinsBuildCreate(
            job_id=job.id if job else None,
            job_name=job_name,
            build_number=build_number,
            build_url=payload.get("build_url") or payload.get("url") or payload.get("build", {}).get("full_url"),
            branch_name=payload.get("branch_name") or payload.get("branch") or payload.get("git_branch"),
            commit_sha=commit_sha,
            status=str(status_value).lower(),
            trigger_user=payload.get("trigger_user") or payload.get("user_name") or payload.get("user"),
            duration_seconds=_duration_seconds(payload),
            started_at=_parse_datetime(payload.get("started_at") or payload.get("timestamp")),
            finished_at=_parse_datetime(payload.get("finished_at")),
            raw_payload=payload,
        ),
    )


def create_jenkins_job(db: Session, payload: DevopsJenkinsJobCreate) -> DevopsJenkinsJob:
    job = DevopsJenkinsJob(**payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_jenkins_job(db: Session, job_id: int, payload: DevopsJenkinsJobUpdate) -> DevopsJenkinsJob:
    job = _get_jenkins_job(db, job_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return job


def delete_jenkins_job(db: Session, job_id: int) -> None:
    job = _get_jenkins_job(db, job_id)
    job.deleted = 1
    job.delete_time = datetime.now()
    db.commit()


def list_commits(db: Session, object_type: str | None = None, object_id: int | None = None) -> list[DevopsCommit]:
    query = db.query(DevopsCommit).filter(DevopsCommit.deleted == 0)
    if object_type and object_id:
        query = query.join(DevopsCommitLink, DevopsCommitLink.commit_id == DevopsCommit.id).filter(
            DevopsCommitLink.object_type == object_type,
            DevopsCommitLink.object_id == object_id,
        )
    return query.order_by(DevopsCommit.committed_at.desc(), DevopsCommit.id.desc()).all()


def get_commit_detail(db: Session, commit_id: int) -> dict[str, Any]:
    commit = _get_commit(db, commit_id)
    return {
        **_commit_to_dict(commit),
        "diff_text": commit.diff_text,
        "diff_json": commit.diff_json,
        "links": _commit_links(db, commit.id),
    }


def ingest_commit(db: Session, payload: DevopsCommitIngest) -> DevopsCommit:
    data = payload.model_dump()
    data["short_sha"] = data.get("short_sha") or data["commit_sha"][:8]
    data["title"] = data.get("title") or _first_line(data.get("message")) or data["short_sha"]
    commit = (
        db.query(DevopsCommit)
        .filter(
            DevopsCommit.provider == data["provider"],
            DevopsCommit.repository_id == data.get("repository_id"),
            DevopsCommit.commit_sha == data["commit_sha"],
        )
        .first()
    )
    if commit:
        for field, value in data.items():
            setattr(commit, field, value)
    else:
        commit = DevopsCommit(**data)
        db.add(commit)
        db.flush()

    links = resolve_commit_references(db, f"{commit.title or ''}\n{commit.message or ''}")
    for link in links:
        _ensure_commit_link(db, commit.id, link["object_type"], link["object_id"])
    _ensure_review_task(db, commit, links)
    db.commit()
    db.refresh(commit)
    return commit


def ingest_gitlab_webhook(db: Session, payload: dict[str, Any]) -> list[DevopsCommit]:
    commits = payload.get("commits") or []
    project = payload.get("project") or {}
    repository = payload.get("repository") or {}
    branch_name = _ref_to_branch(payload.get("ref"))
    result = []
    repo = _find_or_create_repository_from_webhook(db, project, repository)
    for item in commits:
        author = item.get("author") or {}
        result.append(
            ingest_commit(
                db,
                DevopsCommitIngest(
                    provider="gitlab",
                    repository_id=repo.id if repo else None,
                    external_project_id=str(project.get("id")) if project.get("id") is not None else None,
                    commit_sha=item.get("id") or item.get("sha"),
                    short_sha=(item.get("id") or item.get("sha") or "")[:8],
                    branch_name=branch_name,
                    title=item.get("title") or _first_line(item.get("message")),
                    message=item.get("message"),
                    author_name=author.get("name"),
                    author_email=author.get("email"),
                    committed_at=_parse_datetime(item.get("timestamp")),
                    web_url=item.get("url"),
                    diff_text=item.get("diff_text"),
                    diff_json=item.get("diffs") or item.get("diff_json"),
                    raw_payload=item,
                ),
            )
        )
    return result


def resolve_commit_references(db: Session, message: str) -> list[dict[str, int | str]]:
    found: list[dict[str, int | str]] = []
    seen = set()
    for object_type, pattern in REFERENCE_PATTERNS:
        for match in pattern.finditer(message or ""):
            object_id = int(match.group(1))
            key = (object_type, object_id)
            if key in seen or not _object_exists(db, object_type, object_id):
                continue
            seen.add(key)
            found.append({"object_type": object_type, "object_id": object_id})
    return found


def list_review_tasks(db: Session, status_value: str | None = None) -> list[dict[str, Any]]:
    query = db.query(DevopsCodeReviewTask).order_by(DevopsCodeReviewTask.id.desc())
    if status_value:
        query = query.filter(DevopsCodeReviewTask.status == status_value)
    tasks = query.all()
    commit_ids = [item.commit_id for item in tasks]
    commits = {
        item.id: item
        for item in db.query(DevopsCommit).filter(DevopsCommit.id.in_(commit_ids)).all()
    } if commit_ids else {}
    return [
        {
            "id": task.id,
            "commit_id": task.commit_id,
            "title": task.title,
            "owner_id": task.owner_id,
            "status": task.status,
            "create_time": task.create_time,
            "finish_time": task.finish_time,
            "commit": _commit_to_dict(commits[task.commit_id]) if task.commit_id in commits else None,
            "links": _commit_links(db, task.commit_id),
        }
        for task in tasks
    ]


def mark_commit_reviewed(db: Session, commit_id: int, payload: DevopsReviewRequest) -> DevopsCommit:
    commit = _get_commit(db, commit_id)
    commit.review_status = "reviewed"
    commit.reviewer_id = payload.reviewer_id
    commit.review_time = datetime.now()
    commit.review_remark = payload.remark
    task = db.query(DevopsCodeReviewTask).filter(DevopsCodeReviewTask.commit_id == commit.id).first()
    if task:
        task.status = "reviewed"
        task.finish_time = commit.review_time
    db.commit()
    db.refresh(commit)
    return commit


def _get_repository(db: Session, repository_id: int) -> DevopsRepository:
    repo = db.query(DevopsRepository).filter(DevopsRepository.id == repository_id, DevopsRepository.deleted == 0).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return repo


def _get_jenkins_job(db: Session, job_id: int) -> DevopsJenkinsJob:
    job = db.query(DevopsJenkinsJob).filter(DevopsJenkinsJob.id == job_id, DevopsJenkinsJob.deleted == 0).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jenkins job not found")
    return job


def _find_jenkins_job_by_name(db: Session, job_name: str) -> DevopsJenkinsJob | None:
    return (
        db.query(DevopsJenkinsJob)
        .filter(DevopsJenkinsJob.job_name == job_name, DevopsJenkinsJob.deleted == 0)
        .first()
    )


def _commit_id_for_sha(db: Session, commit_sha: str | None) -> int | None:
    if not commit_sha:
        return None
    commit = (
        db.query(DevopsCommit)
        .filter(DevopsCommit.commit_sha == commit_sha, DevopsCommit.deleted == 0)
        .first()
    )
    return commit.id if commit else None


def _duration_seconds(payload: dict[str, Any]) -> int | None:
    value = payload.get("duration_seconds") or payload.get("duration")
    if value is None and isinstance(payload.get("build"), dict):
        value = payload["build"].get("duration")
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number // 1000 if number > 100000 else number


def _get_commit(db: Session, commit_id: int) -> DevopsCommit:
    commit = db.query(DevopsCommit).filter(DevopsCommit.id == commit_id, DevopsCommit.deleted == 0).first()
    if not commit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commit not found")
    return commit


def _ensure_commit_link(db: Session, commit_id: int, object_type: str, object_id: int) -> None:
    exists = db.query(DevopsCommitLink).filter(
        DevopsCommitLink.commit_id == commit_id,
        DevopsCommitLink.object_type == object_type,
        DevopsCommitLink.object_id == object_id,
    ).first()
    if not exists:
        db.add(DevopsCommitLink(commit_id=commit_id, object_type=object_type, object_id=object_id))


def _ensure_review_task(db: Session, commit: DevopsCommit, links: list[dict[str, Any]]) -> None:
    task = db.query(DevopsCodeReviewTask).filter(DevopsCodeReviewTask.commit_id == commit.id).first()
    owner_id = _development_lead_user_id(db) or _first_owner_id(db, links)
    if task:
        task.title = f"Code Review: {commit.short_sha or commit.commit_sha[:8]} {commit.title or ''}".strip()
        if not task.owner_id:
            task.owner_id = owner_id
        return
    db.add(
        DevopsCodeReviewTask(
            commit_id=commit.id,
            title=f"Code Review: {commit.short_sha or commit.commit_sha[:8]} {commit.title or ''}".strip(),
            owner_id=owner_id,
        )
    )


def _development_lead_user_id(db: Session) -> int | None:
    row = (
        db.query(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(
            User.deleted == 0,
            User.is_active.is_(True),
            Role.enabled.is_(True),
            Role.role_key == "development_lead",
        )
        .order_by(User.id.asc())
        .first()
    )
    return row.id if row else None


def _first_owner_id(db: Session, links: list[dict[str, Any]]) -> int | None:
    for link in links:
        model = {"requirement": Requirement, "task": Task, "bug": Bug}.get(str(link["object_type"]))
        if not model:
            continue
        item = db.query(model).filter(model.id == link["object_id"]).first()
        owner_id = getattr(item, "owner_id", None) if item else None
        if owner_id:
            return owner_id
    return None


def _object_exists(db: Session, object_type: str, object_id: int) -> bool:
    model = {"requirement": Requirement, "task": Task, "bug": Bug}.get(object_type)
    if not model:
        return False
    return db.query(model).filter(model.id == object_id, model.deleted == 0).first() is not None


def _commit_links(db: Session, commit_id: int) -> list[dict[str, Any]]:
    return [
        {"object_type": item.object_type, "object_id": item.object_id}
        for item in db.query(DevopsCommitLink).filter(DevopsCommitLink.commit_id == commit_id).all()
    ]


def _commit_to_dict(commit: DevopsCommit) -> dict[str, Any]:
    return {
        "id": commit.id,
        "provider": commit.provider,
        "repository_id": commit.repository_id,
        "external_project_id": commit.external_project_id,
        "commit_sha": commit.commit_sha,
        "short_sha": commit.short_sha,
        "branch_name": commit.branch_name,
        "title": commit.title,
        "message": commit.message,
        "author_name": commit.author_name,
        "author_email": commit.author_email,
        "committed_at": commit.committed_at,
        "web_url": commit.web_url,
        "review_status": commit.review_status,
        "reviewer_id": commit.reviewer_id,
        "review_time": commit.review_time,
        "review_remark": commit.review_remark,
        "create_time": commit.create_time,
    }


def _find_or_create_repository_from_webhook(db: Session, project: dict[str, Any], repository: dict[str, Any]) -> DevopsRepository | None:
    project_id = project.get("id")
    if project_id is None:
        return None
    repo = (
        db.query(DevopsRepository)
        .filter(DevopsRepository.provider == "gitlab", DevopsRepository.external_project_id == str(project_id), DevopsRepository.deleted == 0)
        .first()
    )
    if repo:
        return repo
    repo = DevopsRepository(
        provider="gitlab",
        name=project.get("name") or repository.get("name") or f"GitLab {project_id}",
        repository_url=project.get("web_url") or repository.get("homepage"),
        external_project_id=str(project_id),
        default_branch=project.get("default_branch"),
    )
    db.add(repo)
    db.flush()
    return repo


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _ref_to_branch(ref: str | None) -> str | None:
    return ref.rsplit("/", 1)[-1] if ref else None


def _first_line(value: str | None) -> str | None:
    return (value or "").strip().splitlines()[0] if (value or "").strip() else None

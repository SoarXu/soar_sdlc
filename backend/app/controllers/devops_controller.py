from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import devops_service
from app.views.devops_view import (
    DevopsCommitDetail,
    DevopsCommitIngest,
    DevopsCommitRead,
    DevopsJenkinsBuildCreate,
    DevopsJenkinsBuildRead,
    DevopsJenkinsJobCreate,
    DevopsJenkinsJobRead,
    DevopsJenkinsJobUpdate,
    DevopsRepositoryCreate,
    DevopsRepositoryRead,
    DevopsRepositoryUpdate,
    DevopsReviewRequest,
)

router = APIRouter()


@router.get("/repositories", response_model=list[DevopsRepositoryRead])
def list_repositories(db: Session = Depends(get_db)):
    return devops_service.list_repositories(db)


@router.post("/repositories", response_model=DevopsRepositoryRead, status_code=status.HTTP_201_CREATED)
def create_repository(payload: DevopsRepositoryCreate, db: Session = Depends(get_db)):
    return devops_service.create_repository(db, payload)


@router.put("/repositories/{repository_id}", response_model=DevopsRepositoryRead)
def update_repository(repository_id: int, payload: DevopsRepositoryUpdate, db: Session = Depends(get_db)):
    return devops_service.update_repository(db, repository_id, payload)


@router.delete("/repositories/{repository_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(repository_id: int, db: Session = Depends(get_db)):
    devops_service.delete_repository(db, repository_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/jenkins-jobs", response_model=list[DevopsJenkinsJobRead])
def list_jenkins_jobs(db: Session = Depends(get_db)):
    return devops_service.list_jenkins_jobs(db)


@router.get("/jenkins-builds", response_model=list[DevopsJenkinsBuildRead])
def list_jenkins_builds(job_id: int | None = None, commit_sha: str | None = None, db: Session = Depends(get_db)):
    return devops_service.list_jenkins_builds(db, job_id, commit_sha)


@router.post("/jenkins-builds", response_model=DevopsJenkinsBuildRead, status_code=status.HTTP_201_CREATED)
def create_jenkins_build(payload: DevopsJenkinsBuildCreate, db: Session = Depends(get_db)):
    return devops_service.create_jenkins_build(db, payload)


@router.post("/jenkins/webhook", response_model=DevopsJenkinsBuildRead)
def jenkins_webhook(payload: dict[str, Any], db: Session = Depends(get_db)):
    return devops_service.ingest_jenkins_webhook(db, payload)


@router.post("/jenkins-jobs", response_model=DevopsJenkinsJobRead, status_code=status.HTTP_201_CREATED)
def create_jenkins_job(payload: DevopsJenkinsJobCreate, db: Session = Depends(get_db)):
    return devops_service.create_jenkins_job(db, payload)


@router.put("/jenkins-jobs/{job_id}", response_model=DevopsJenkinsJobRead)
def update_jenkins_job(job_id: int, payload: DevopsJenkinsJobUpdate, db: Session = Depends(get_db)):
    return devops_service.update_jenkins_job(db, job_id, payload)


@router.delete("/jenkins-jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_jenkins_job(job_id: int, db: Session = Depends(get_db)):
    devops_service.delete_jenkins_job(db, job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/commits", response_model=list[DevopsCommitRead])
def list_commits(object_type: str | None = None, object_id: int | None = None, db: Session = Depends(get_db)):
    return devops_service.list_commits(db, object_type, object_id)


@router.get("/commits/{commit_id}", response_model=DevopsCommitDetail)
def get_commit_detail(commit_id: int, db: Session = Depends(get_db)):
    return devops_service.get_commit_detail(db, commit_id)


@router.post("/commits", response_model=DevopsCommitRead, status_code=status.HTTP_201_CREATED)
def ingest_commit(payload: DevopsCommitIngest, db: Session = Depends(get_db)):
    return devops_service.ingest_commit(db, payload)


@router.post("/gitlab/webhook", response_model=list[DevopsCommitRead])
def gitlab_webhook(payload: dict[str, Any], db: Session = Depends(get_db)):
    return devops_service.ingest_gitlab_webhook(db, payload)


@router.get("/review-tasks")
def list_review_tasks(status_value: str | None = None, db: Session = Depends(get_db)):
    return devops_service.list_review_tasks(db, status_value)


@router.post("/commits/{commit_id}/reviewed", response_model=DevopsCommitRead)
def mark_commit_reviewed(commit_id: int, payload: DevopsReviewRequest, db: Session = Depends(get_db)):
    return devops_service.mark_commit_reviewed(db, commit_id, payload)

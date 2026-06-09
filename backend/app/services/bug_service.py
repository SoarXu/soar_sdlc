from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.test_run import TestRunCase
from app.views.bug_view import BugCreate, BugFromTestRunCaseRequest, BugUpdate


def list_bugs(db: Session) -> list[Bug]:
    return db.query(Bug).filter(Bug.delete_time.is_(None)).order_by(Bug.id.desc()).all()


def create_bug(db: Session, payload: BugCreate) -> Bug:
    bug = Bug(**payload.model_dump())
    db.add(bug)
    db.commit()
    db.refresh(bug)
    return bug


def create_bug_from_test_run_case(db: Session, run_case_id: int, payload: BugFromTestRunCaseRequest) -> Bug:
    run_case = db.query(TestRunCase).filter(TestRunCase.id == run_case_id).first()
    if not run_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run case not found")
    if run_case.result != "failed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only failed test results can create bugs")

    test_case = db.query(TestCase).filter(TestCase.id == run_case.test_case_id).first()
    test_run = db.query(TestRun).filter(TestRun.id == run_case.test_run_id).first()
    if not test_case or not test_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test context not found")

    requirement = (
        db.query(Requirement).filter(Requirement.id == test_case.requirement_id, Requirement.delete_time.is_(None)).first()
        if test_case.requirement_id
        else None
    )
    project = db.query(Project).filter(Project.id == test_run.project_id, Project.delete_time.is_(None)).first()
    owner_id = requirement.owner_id if requirement and requirement.owner_id else project.owner_id if project else None

    bug = Bug(
        project_id=test_run.project_id,
        requirement_id=test_case.requirement_id,
        test_case_id=test_case.id,
        test_run_id=test_run.id,
        title=payload.title,
        severity=payload.severity,
        priority=payload.priority,
        owner_id=owner_id,
        reporter_id=payload.reporter_id or run_case.tester_id,
        reproduce_steps=payload.reproduce_steps,
        expected_result=payload.expected_result or test_case.expected_result,
        actual_result=payload.actual_result,
        status="open",
    )
    db.add(bug)
    db.commit()
    db.refresh(bug)
    return bug


def update_bug(db: Session, bug_id: int, payload: BugUpdate) -> Bug:
    bug = _get_active_bug(db, bug_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(bug, field, value)
    db.commit()
    db.refresh(bug)
    return bug


def delete_bug(db: Session, bug_id: int) -> None:
    bug = _get_active_bug(db, bug_id)
    bug.delete_time = datetime.now()
    db.commit()


def _get_active_bug(db: Session, bug_id: int) -> Bug:
    bug = db.query(Bug).filter(Bug.id == bug_id, Bug.delete_time.is_(None)).first()
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug not found")
    return bug

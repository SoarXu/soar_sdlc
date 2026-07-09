from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.test_case import TestCase
from app.models.test_run import TestRun, TestRunCase
from app.services.current_handler_service import ensure_work_item_action
from app.services.lifecycle_service import (
    project_lifecycle_phase,
    requirement_lifecycle_phase,
    test_case_lifecycle_phase,
)
from app.services.status_operation_service import list_status_operations
from app.views.bug_view import BugCreate, BugFromTestRunCaseRequest, BugUpdate


def list_bugs(db: Session) -> list[Bug]:
    return db.query(Bug).filter(Bug.deleted == 0).order_by(Bug.id.desc()).all()


def get_bug(db: Session, bug_id: int) -> Bug:
    return _get_active_bug(db, bug_id)


def create_bug(db: Session, payload: BugCreate) -> Bug:
    data = payload.model_dump()
    if data.get("iteration_id"):
        _ensure_iteration_can_accept_bug(db, data["iteration_id"], data.get("project_id"))
    data["lifecycle_phase"] = (
        requirement_lifecycle_phase(db, data.get("requirement_id"))
        or test_case_lifecycle_phase(db, data.get("test_case_id"))
        or project_lifecycle_phase(db, data.get("project_id"))
    )
    if data.get("status") not in {"pending_handling", "fixing", "pending_verification", "verified", "closed"}:
        data["status"] = "pending_handling"
    bug = Bug(**data)
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
        db.query(Requirement).filter(Requirement.id == test_case.requirement_id, Requirement.deleted == 0).first()
        if test_case.requirement_id
        else None
    )
    bug = Bug(
        project_id=test_run.project_id,
        requirement_id=test_case.requirement_id,
        test_case_id=test_case.id,
        test_run_id=test_run.id,
        title=payload.title,
        severity=payload.severity,
        priority=payload.priority,
        owner_id=requirement.owner_id if requirement else None,
        reporter_id=payload.reporter_id or run_case.tester_id,
        reproduce_steps=payload.reproduce_steps,
        expected_result=payload.expected_result or test_case.expected_result,
        actual_result=payload.actual_result,
        status="pending_handling",
        lifecycle_phase=test_case.lifecycle_phase,
    )
    db.add(bug)
    db.commit()
    db.refresh(bug)
    return bug


def update_bug(db: Session, bug_id: int, payload: BugUpdate, actor_id: int | None = None) -> Bug:
    bug = _get_active_bug(db, bug_id)
    ensure_work_item_action(db, bug, actor_id, "Bug")
    data = payload.model_dump(exclude_unset=True)
    data.pop("status", None)
    data.pop("resolution", None)
    data.pop("verify_result", None)
    data.pop("close_reason", None)
    if data.get("iteration_id"):
        _ensure_iteration_can_accept_bug(db, data["iteration_id"], data.get("project_id", bug.project_id))
    for field, value in data.items():
        setattr(bug, field, value)
    db.commit()
    db.refresh(bug)
    return bug


def list_bug_status_operations(db: Session, bug_id: int) -> list[dict]:
    _get_active_bug(db, bug_id)
    return list_status_operations(db, "bug", bug_id)


def delete_bug(db: Session, bug_id: int) -> None:
    bug = _get_active_bug(db, bug_id)
    bug.deleted = 1
    bug.delete_time = datetime.now()
    db.commit()


def _get_active_bug(db: Session, bug_id: int) -> Bug:
    bug = db.query(Bug).filter(Bug.id == bug_id, Bug.deleted == 0).first()
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug not found")
    return bug


def _ensure_iteration_can_accept_bug(db: Session, iteration_id: int, bug_project_id: int | None) -> None:
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    if not iteration:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Iteration not found")
    if iteration.status in {"finished", "closed", "completed", "canceled"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Closed iteration cannot accept bugs")
    project_ids = {item.project_id for item in db.query(IterationProject).filter(IterationProject.iteration_id == iteration_id).all()}
    scoped_project_ids = set(project_ids)
    for iteration_project_id in project_ids:
        scoped_project_ids.update(_collect_descendant_project_ids(db, iteration_project_id))
    if bug_project_id not in scoped_project_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Iteration is outside bug project scope")


def _collect_descendant_project_ids(db: Session, project_id: int) -> set[int]:
    children = db.query(Project).filter(Project.parent_id == project_id, Project.deleted == 0).all()
    result = {child.id for child in children}
    for child in children:
        result.update(_collect_descendant_project_ids(db, child.id))
    return result

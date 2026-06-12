from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.test_run import TestRunCase
from app.services.lifecycle_service import (
    project_lifecycle_phase,
    requirement_lifecycle_phase,
    test_case_lifecycle_phase,
)
from app.services.status_operation_service import create_status_operation, list_status_operations
from app.views.bug_view import BugCreate, BugFromTestRunCaseRequest, BugStatusActionRequest, BugUpdate

BUG_RESOLUTIONS = {"设计如此", "重复Bug", "外部原因", "已解决", "无法重现", "延期处理", "不予解决"}


def list_bugs(db: Session) -> list[Bug]:
    return db.query(Bug).filter(Bug.deleted == 0).order_by(Bug.id.desc()).all()


def get_bug(db: Session, bug_id: int) -> Bug:
    return _get_active_bug(db, bug_id)


def create_bug(db: Session, payload: BugCreate) -> Bug:
    data = payload.model_dump()
    data["lifecycle_phase"] = (
        requirement_lifecycle_phase(db, data.get("requirement_id"))
        or test_case_lifecycle_phase(db, data.get("test_case_id"))
        or project_lifecycle_phase(db, data.get("project_id"))
    )
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
    project = db.query(Project).filter(Project.id == test_run.project_id, Project.deleted == 0).first()
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
        lifecycle_phase=test_case.lifecycle_phase,
    )
    db.add(bug)
    db.commit()
    db.refresh(bug)
    return bug


def update_bug(db: Session, bug_id: int, payload: BugUpdate) -> Bug:
    bug = _get_active_bug(db, bug_id)
    data = payload.model_dump(exclude_unset=True)
    data.pop("status", None)
    data.pop("resolution", None)
    data.pop("verify_result", None)
    data.pop("close_reason", None)
    for field, value in data.items():
        setattr(bug, field, value)
    db.commit()
    db.refresh(bug)
    return bug


def start_fixing_bug(db: Session, bug_id: int, payload: BugStatusActionRequest | None = None) -> Bug:
    bug = _get_active_bug(db, bug_id)
    _require_bug_status(bug, {"open", "reopened", "suspended"}, "只有待修复、重新打开或已挂起的 Bug 可以开始修复")
    if payload and payload.iteration_id:
        _ensure_iteration_can_fix_bug(db, payload.iteration_id, bug)
        bug.iteration_id = payload.iteration_id
    return _transition_bug(db, bug, "fixing", "start_fixing", payload)


def resolve_bug(db: Session, bug_id: int, payload: BugStatusActionRequest) -> Bug:
    if not payload.resolution:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="解决结果必填")
    if payload.resolution not in BUG_RESOLUTIONS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="未知的解决方案")
    bug = _get_active_bug(db, bug_id)
    _require_bug_status(bug, {"fixing"}, "只有修复中的 Bug 可以提交解决")
    bug.resolution = payload.resolution
    bug.resolve_time = payload.effective_time or datetime.now()
    bug.resolved_by = payload.operator_id
    return _transition_bug(db, bug, "verifying", "resolve", payload)


def start_verifying_bug(db: Session, bug_id: int, payload: BugStatusActionRequest | None = None) -> Bug:
    bug = _get_active_bug(db, bug_id)
    _require_bug_status(bug, {"resolved"}, "只有已解决的 Bug 可以开始验证")
    return _transition_bug(db, bug, "verifying", "start_verifying", payload)


def verify_bug_passed(db: Session, bug_id: int, payload: BugStatusActionRequest | None = None) -> Bug:
    bug = _get_active_bug(db, bug_id)
    _require_bug_status(bug, {"verifying"}, "只有待验证的 Bug 可以验证通过")
    action_payload = payload or BugStatusActionRequest()
    bug.verify_result = action_payload.verify_result or "passed"
    bug.verify_time = action_payload.effective_time or datetime.now()
    bug.verified_by = action_payload.operator_id
    bug.close_reason = action_payload.reason or "verified"
    return _transition_bug(db, bug, "closed", "verify_passed", action_payload)


def verify_bug_failed(db: Session, bug_id: int, payload: BugStatusActionRequest | None = None) -> Bug:
    bug = _get_active_bug(db, bug_id)
    _require_bug_status(bug, {"verifying", "resolved"}, "只有已解决或待验证的 Bug 可以验证失败")
    action_payload = payload or BugStatusActionRequest()
    bug.verify_result = action_payload.verify_result or "failed"
    bug.verify_time = action_payload.effective_time or datetime.now()
    bug.verified_by = action_payload.operator_id
    bug.reopen_count = (bug.reopen_count or 0) + 1
    return _transition_bug(db, bug, "reopened", "verify_failed", action_payload)


def suspend_bug(db: Session, bug_id: int, payload: BugStatusActionRequest | None = None) -> Bug:
    bug = _get_active_bug(db, bug_id)
    _require_bug_status(bug, {"open", "fixing", "reopened"}, "只有待修复、修复中或重新打开的 Bug 可以挂起")
    return _transition_bug(db, bug, "suspended", "suspend", payload)


def close_bug(db: Session, bug_id: int, payload: BugStatusActionRequest | None = None) -> Bug:
    bug = _get_active_bug(db, bug_id)
    _require_bug_status(bug, {"open", "suspended", "verifying"}, "只有待确认、已挂起或待验证的 Bug 可以关闭")
    action_payload = payload or BugStatusActionRequest()
    if bug.status == "verifying":
        bug.verify_result = action_payload.verify_result or "passed"
        bug.verify_time = action_payload.effective_time or datetime.now()
        bug.verified_by = action_payload.operator_id
    bug.close_reason = action_payload.reason
    return _transition_bug(db, bug, "closed", "close", action_payload)


def activate_bug(db: Session, bug_id: int, payload: BugStatusActionRequest | None = None) -> Bug:
    bug = _get_active_bug(db, bug_id)
    _require_bug_status(bug, {"verifying", "closed"}, "只有待验证或已关闭的 Bug 可以激活")
    action_payload = payload or BugStatusActionRequest()
    if bug.status == "verifying":
        bug.verify_result = action_payload.verify_result or "failed"
        bug.verify_time = action_payload.effective_time or datetime.now()
        bug.verified_by = action_payload.operator_id
    bug.reopen_count = (bug.reopen_count or 0) + 1
    return _transition_bug(db, bug, "fixing", "activate", action_payload)


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


def _transition_bug(
    db: Session,
    bug: Bug,
    target_status: str,
    action: str,
    payload: BugStatusActionRequest | None,
) -> Bug:
    from_status = bug.status
    bug.status = target_status
    create_status_operation(
        db,
        object_type="bug",
        object_id=bug.id,
        action=action,
        from_status=from_status,
        to_status=target_status,
        payload=payload,
        actor_id=payload.operator_id if payload else None,
    )
    db.commit()
    db.refresh(bug)
    return bug


def _require_bug_status(bug: Bug, allowed_statuses: set[str], message: str) -> None:
    if bug.status not in allowed_statuses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _ensure_iteration_can_fix_bug(db: Session, iteration_id: int, bug: Bug) -> None:
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    if not iteration:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="解决迭代不存在")
    project_ids = {
        item.project_id
        for item in db.query(IterationProject).filter(IterationProject.iteration_id == iteration_id).all()
    }
    scoped_project_ids = set(project_ids)
    for project_id in project_ids:
        scoped_project_ids.update(_collect_descendant_project_ids(db, project_id))
    if bug.project_id not in scoped_project_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="解决迭代不包含该 Bug 所属项目")


def _collect_descendant_project_ids(db: Session, project_id: int) -> set[int]:
    children = db.query(Project).filter(Project.parent_id == project_id, Project.deleted == 0).all()
    result = {child.id for child in children}
    for child in children:
        result.update(_collect_descendant_project_ids(db, child.id))
    return result

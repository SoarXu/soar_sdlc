from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.requirement import Requirement
from app.models.task import Task
from app.services.handler_transition_rule_service import apply_handler_transition
from app.models.test_case import TestCase
from app.services.status_operation_service import create_status_operation


PASSING_TEST_RESULTS = {"passed", "ignored"}
def submit_requirement_validation(db: Session, requirement: Requirement, actor_id: int | None = None) -> Requirement:
    _require_finished_tasks(db, requirement.id)
    if requirement.status == "done":
        return requirement
    if requirement.status == "validation_failed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证未通过的需求请处理关联 Bug，不允许手工重新提交验证")
    from_status = requirement.status
    requirement.status = "pending_validation"
    create_status_operation(
        db,
        object_type="requirement",
        object_id=requirement.id,
        action="submit_validation",
        from_status=from_status,
        to_status=requirement.status,
        payload=None,
        actor_id=actor_id,
    )
    apply_handler_transition(
        db,
        item=requirement,
        object_type="requirement",
        action="submit_validation",
        from_status=from_status,
        to_status=requirement.status,
        actor_id=actor_id,
    )
    return requirement


def apply_test_execution_result(db: Session, test_case: TestCase, result: str, actor_id: int | None = None) -> None:
    if not test_case.requirement_id:
        return
    requirement = _get_requirement(db, test_case.requirement_id)
    if not requirement or requirement.status not in {"pending_validation", "validation_failed"}:
        return
    if result in {"failed", "blocked"} and requirement.status == "pending_validation":
        _transition_requirement(db, requirement, "validation_failed", "validation_failed", actor_id=actor_id)
        return
    evaluate_requirement_validation(db, requirement.id, actor_id=actor_id)


def evaluate_requirement_validation(db: Session, requirement_id: int, actor_id: int | None = None) -> Requirement | None:
    requirement = _get_requirement(db, requirement_id)
    if not requirement or requirement.status not in {"pending_validation", "validation_failed"}:
        return requirement
    if _all_related_test_cases_passed(db, requirement.id):
        _transition_requirement(db, requirement, "done", "validation_passed", actor_id=actor_id)
    return requirement


def _require_finished_tasks(db: Session, requirement_id: int) -> None:
    open_tasks = (
        db.query(Task)
        .filter(Task.requirement_id == requirement_id, Task.deleted == 0, Task.status.notin_(["done", "closed"]))
        .count()
    )
    if open_tasks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="存在关联任务未完成，需求不允许提交验证")


def _all_related_test_cases_passed(db: Session, requirement_id: int) -> bool:
    test_cases = db.query(TestCase).filter(TestCase.requirement_id == requirement_id, TestCase.deleted == 0).all()
    if not test_cases:
        return False
    return all(test_case.last_execute_result in PASSING_TEST_RESULTS for test_case in test_cases)


def _get_requirement(db: Session, requirement_id: int) -> Requirement | None:
    return db.query(Requirement).filter(Requirement.id == requirement_id, Requirement.deleted == 0).first()


def _transition_requirement(
    db: Session,
    requirement: Requirement,
    target_status: str,
    action: str,
    actor_id: int | None = None,
) -> None:
    if requirement.status == target_status:
        return
    from_status = requirement.status
    requirement.status = target_status
    create_status_operation(
        db,
        object_type="requirement",
        object_id=requirement.id,
        action=action,
        from_status=from_status,
        to_status=target_status,
        payload=None,
        actor_id=actor_id,
    )
    apply_handler_transition(
        db,
        item=requirement,
        object_type="requirement",
        action=action,
        from_status=from_status,
        to_status=target_status,
        actor_id=actor_id,
    )

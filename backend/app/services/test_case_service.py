from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.test_case import TestCase
from app.models.test_case_execution import TestCaseExecutionLog
from app.views.test_case_view import TestCaseCreate, TestCaseExecutionCreate, TestCaseUpdate


def list_test_cases(db: Session) -> list[TestCase]:
    return db.query(TestCase).filter(TestCase.deleted == 0).order_by(TestCase.id.desc()).all()


def create_test_case(db: Session, payload: TestCaseCreate) -> TestCase:
    test_case = TestCase(**payload.model_dump())
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    return test_case


def update_test_case(db: Session, test_case_id: int, payload: TestCaseUpdate) -> TestCase:
    test_case = _get_active_test_case(db, test_case_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(test_case, field, value)
    db.commit()
    db.refresh(test_case)
    return test_case


def delete_test_case(db: Session, test_case_id: int) -> None:
    test_case = _get_active_test_case(db, test_case_id)
    test_case.deleted = 1
    test_case.delete_time = datetime.now()
    db.commit()


def create_test_case_execution(db: Session, test_case_id: int, payload: TestCaseExecutionCreate) -> TestCaseExecutionLog:
    test_case = _get_active_test_case(db, test_case_id)
    steps_result = payload.steps_result_json or []
    result = _calculate_execution_result(steps_result)
    execute_time = payload.execute_time or datetime.now()
    execution = TestCaseExecutionLog(
        test_case_id=test_case.id,
        executor_id=payload.executor_id,
        execute_time=execute_time,
        result=result,
        steps_result_json=steps_result,
    )
    test_case.last_execute_time = execute_time
    test_case.last_execute_result = result
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def list_test_case_executions(db: Session, test_case_id: int) -> list[TestCaseExecutionLog]:
    _get_active_test_case(db, test_case_id)
    return (
        db.query(TestCaseExecutionLog)
        .filter(TestCaseExecutionLog.test_case_id == test_case_id)
        .order_by(TestCaseExecutionLog.execute_time.desc(), TestCaseExecutionLog.id.desc())
        .all()
    )


def _get_active_test_case(db: Session, test_case_id: int) -> TestCase:
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id, TestCase.deleted == 0).first()
    if not test_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found")
    return test_case


def _calculate_execution_result(steps_result: dict | list | None) -> str:
    rows = steps_result if isinstance(steps_result, list) else []
    values = [row.get("result") for row in rows if isinstance(row, dict)]
    if "failed" in values:
        return "failed"
    if "blocked" in values:
        return "blocked"
    if values and all(value == "ignored" for value in values):
        return "ignored"
    return "passed"

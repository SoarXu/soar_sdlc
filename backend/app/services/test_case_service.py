from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.requirement import Requirement
from app.models.test_case import TestCase
from app.models.test_case_execution import TestCaseExecutionLog
from app.views.test_case_view import BugFromTestCaseRequest, TestCaseCreate, TestCaseExecutionCreate, TestCaseUpdate


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


def create_bug_from_test_case(db: Session, test_case_id: int, payload: BugFromTestCaseRequest) -> Bug:
    test_case = _get_active_test_case(db, test_case_id)
    latest_execution = (
        db.query(TestCaseExecutionLog)
        .filter(TestCaseExecutionLog.test_case_id == test_case.id)
        .order_by(TestCaseExecutionLog.execute_time.desc(), TestCaseExecutionLog.id.desc())
        .first()
    )
    if not latest_execution or latest_execution.result not in {"failed", "blocked"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅失败或阻塞的用例可以提交 Bug")

    requirement = (
        db.query(Requirement).filter(Requirement.id == test_case.requirement_id, Requirement.deleted == 0).first()
        if test_case.requirement_id
        else None
    )
    project_id = requirement.project_id if requirement else test_case.project_id
    if not project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用例未关联项目，无法提交 Bug")

    bug = Bug(
        project_id=project_id,
        iteration_id=requirement.iteration_id if requirement else None,
        requirement_id=requirement.id if requirement else test_case.requirement_id,
        test_case_id=test_case.id,
        title=payload.title,
        bug_type=payload.bug_type,
        severity=payload.severity,
        priority=payload.priority,
        owner_id=requirement.owner_id if requirement else None,
        reporter_id=payload.reporter_id or latest_execution.executor_id,
        reproduce_steps=payload.reproduce_steps or _build_reproduce_steps(test_case, latest_execution),
        expected_result=payload.expected_result or test_case.expected_result,
        actual_result=payload.actual_result or _build_actual_result(latest_execution),
        status="open",
    )
    db.add(bug)
    db.commit()
    db.refresh(bug)
    return bug


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


def _build_reproduce_steps(test_case: TestCase, execution: TestCaseExecutionLog) -> str:
    rows = execution.steps_result_json if isinstance(execution.steps_result_json, list) else []
    lines = ["<p>[步骤]</p>", "<ol>"]
    for row in rows:
        if isinstance(row, dict):
            lines.append(f"<li>{_escape_text(row.get('step'))}</li>")
    lines.append("</ol>")
    lines.append("<p>[结果]</p>")
    lines.append("<ol>")
    for row in rows:
        if isinstance(row, dict):
            result = row.get("result") or "-"
            actual = row.get("actual") or ""
            lines.append(f"<li>{_escape_text(result)} {_escape_text(actual)}</li>")
    lines.append("</ol>")
    lines.append("<p>[期望]</p>")
    lines.append("<ol>")
    for row in rows:
        if isinstance(row, dict):
            lines.append(f"<li>{_escape_text(row.get('expected'))}</li>")
    lines.append("</ol>")
    if not rows and test_case.expected_result:
        lines.append(f"<p>{_escape_text(test_case.expected_result)}</p>")
    return "".join(lines)


def _build_actual_result(execution: TestCaseExecutionLog) -> str | None:
    rows = execution.steps_result_json if isinstance(execution.steps_result_json, list) else []
    actual_values = [str(row.get("actual")) for row in rows if isinstance(row, dict) and row.get("actual")]
    return "\n".join(actual_values) if actual_values else execution.result


def _escape_text(value) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )

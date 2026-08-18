from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.requirement import Requirement
from app.models.test_case import TestCase
from app.models.test_case_execution import TestCaseExecutionLog
from app.services.lifecycle_service import project_lifecycle_phase, requirement_lifecycle_phase
from app.services.bug_service import _ensure_iteration_can_accept_bug
from app.services.iteration_service import ensure_iteration_assignment_mutable
from app.services.iteration_assignment_service import resolve_work_item_iteration
from app.services.project_team_service import default_tester_id
from app.services.task_service import linked_task_summaries
from app.services.work_item_iteration_history_service import move_work_item_to_iteration
from app.services.workflow_state_service import initial_workflow_values
from app.services.project_permission_service import visible_project_ids
from app.views.test_case_view import BugFromTestCaseRequest, TestCaseCreate, TestCaseExecutionCreate, TestCaseUpdate

VALID_TEST_SCOPES = {
    "unit_test",
    "functional_test",
    "integration_test",
    "system_test",
    "smoke_test",
    "release_validation",
}


def list_test_cases(db: Session, actor) -> list[TestCase]:
    test_cases = db.query(TestCase).filter(
        TestCase.deleted == 0, TestCase.project_id.in_(visible_project_ids(db, actor))
    ).order_by(TestCase.id.desc()).all()
    for test_case in test_cases:
        _normalize_test_scopes(test_case)
        test_case.linked_tasks = linked_task_summaries(db, "test_case", test_case.id)
    return test_cases


def get_test_case(db: Session, test_case_id: int) -> TestCase:
    test_case = _get_active_test_case(db, test_case_id)
    _normalize_test_scopes(test_case)
    test_case.linked_tasks = linked_task_summaries(db, "test_case", test_case.id)
    return test_case


def create_test_case(db: Session, payload: TestCaseCreate) -> TestCase:
    data = payload.model_dump()
    _apply_test_scopes(data, legacy_scope=data.get("test_scope"))
    data["lifecycle_phase"] = (
        requirement_lifecycle_phase(db, data.get("requirement_id"))
        or project_lifecycle_phase(db, data.get("project_id"))
    )
    if not data.get("default_tester_id"):
        data["default_tester_id"] = default_tester_id(db, data.get("project_id"))
    test_case = TestCase(**data)
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    return test_case


def update_test_case(db: Session, test_case_id: int, payload: TestCaseUpdate) -> TestCase:
    test_case = _get_active_test_case(db, test_case_id)
    data = payload.model_dump(exclude_unset=True)
    if "test_scopes" in data or "test_scope" in data:
        _apply_test_scopes(data, legacy_scope=data.get("test_scope", test_case.test_scope))
    for field, value in data.items():
        setattr(test_case, field, value)
    db.commit()
    db.refresh(test_case)
    return test_case


def _apply_test_scopes(data: dict, *, legacy_scope: str | None) -> None:
    scopes = data.get("test_scopes")
    if scopes is None:
        scopes = [legacy_scope] if legacy_scope else []
    normalized = []
    for scope in scopes:
        if scope not in VALID_TEST_SCOPES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="存在不支持的适用范围")
        if scope not in normalized:
            normalized.append(scope)
    data["test_scopes"] = normalized
    data["test_scope"] = normalized[0] if normalized else None


def _normalize_test_scopes(test_case: TestCase) -> None:
    if test_case.test_scopes is None:
        test_case.test_scopes = [test_case.test_scope] if test_case.test_scope else []


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


def create_bug_from_test_case(
    db: Session,
    test_case_id: int,
    payload: BugFromTestCaseRequest,
    actor_id: int | None = None,
) -> Bug:
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

    inherited_iteration_id = resolve_work_item_iteration(
        db,
        project_id,
        None,
        source_iteration_id=test_case.iteration_id or (requirement.iteration_id if requirement else None),
        strict_source_iteration=True,
    )
    ensure_iteration_assignment_mutable(db, None, inherited_iteration_id)
    _ensure_iteration_can_accept_bug(db, inherited_iteration_id, project_id)

    workflow_values = initial_workflow_values(db, "bug", project_id)
    bug = Bug(
        project_id=project_id,
        iteration_id=inherited_iteration_id,
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
        **workflow_values,
        lifecycle_phase=test_case.lifecycle_phase,
        creator_id=actor_id,
    )
    db.add(bug)
    db.flush()
    if bug.iteration_id:
        move_work_item_to_iteration(
            db,
            bug,
            bug.iteration_id,
            actor_id=actor_id,
            reason="test_case_bug_created",
        )
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

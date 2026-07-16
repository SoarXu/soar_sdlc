from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.requirement import Requirement
from app.models.test_case import TestCase
from app.services.workflow_state_query_service import non_terminal_state_clause


PASSING_RESULTS = {"passed", "ignored"}
FAILING_RESULTS = {"failed", "blocked"}


def requirement_validation_cases(db: Session, requirement_id: int) -> dict:
    requirement = db.query(Requirement).filter(Requirement.id == requirement_id, Requirement.deleted == 0).first()
    if not requirement:
        return {"summary": _summary([]), "items": []}
    cases = (
        db.query(TestCase)
        .filter(TestCase.requirement_id == requirement.id, TestCase.deleted == 0)
        .order_by(TestCase.id.asc())
        .all()
    )
    items = [_case_item(db, case) for case in cases]
    return {"summary": _summary(items), "items": items}


def bug_validation_context(db: Session, bug_id: int) -> dict:
    bug = db.query(Bug).filter(Bug.id == bug_id, Bug.deleted == 0).first()
    if not bug:
        return {"source": "none", "requirement_id": None, "test_case_id": None, "summary": _summary([]), "items": []}
    if bug.test_case_id:
        test_case = (
            db.query(TestCase)
            .filter(TestCase.id == bug.test_case_id, TestCase.deleted == 0)
            .first()
        )
        items = [_case_item(db, test_case)] if test_case else []
        return {
            "source": "test_case",
            "requirement_id": bug.requirement_id,
            "test_case_id": bug.test_case_id,
            "summary": _summary(items),
            "items": items,
        }
    if bug.requirement_id:
        data = requirement_validation_cases(db, bug.requirement_id)
        return {
            "source": "requirement",
            "requirement_id": bug.requirement_id,
            "test_case_id": None,
            "summary": data["summary"],
            "items": data["items"],
        }
    return {"source": "none", "requirement_id": None, "test_case_id": None, "summary": _summary([]), "items": []}


def _case_item(db: Session, test_case: TestCase) -> dict:
    return {
        "id": test_case.id,
        "project_id": test_case.project_id,
        "requirement_id": test_case.requirement_id,
        "iteration_id": test_case.iteration_id,
        "title": test_case.title,
        "case_type": test_case.case_type,
        "test_scope": test_case.test_scope,
        "default_tester_id": test_case.default_tester_id,
        "latest_execute_time": test_case.last_execute_time,
        "latest_result": test_case.last_execute_result,
        "open_bug_count": _open_bug_count(db, test_case.id),
    }


def _open_bug_count(db: Session, test_case_id: int) -> int:
    return (
        db.query(Bug)
        .filter(Bug.test_case_id == test_case_id, Bug.deleted == 0, non_terminal_state_clause(Bug))
        .count()
    )


def _summary(items: list[dict]) -> dict:
    summary = {"total": len(items), "passed": 0, "failed": 0, "blocked": 0, "ignored": 0, "pending": 0}
    for item in items:
        result = item.get("latest_result")
        if result in PASSING_RESULTS or result in FAILING_RESULTS:
            summary[result] += 1
        else:
            summary["pending"] += 1
    return summary

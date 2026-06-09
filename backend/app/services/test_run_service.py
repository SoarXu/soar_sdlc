from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.test_run import TestRun, TestRunCase
from app.views.test_run_view import SelectTestCasesRequest, TestRunCaseUpdate, TestRunCreate, TestRunUpdate


def list_test_runs(db: Session) -> list[TestRun]:
    return db.query(TestRun).filter(TestRun.delete_time.is_(None)).order_by(TestRun.id.desc()).all()


def create_test_run(db: Session, payload: TestRunCreate) -> TestRun:
    test_run = TestRun(**payload.model_dump())
    db.add(test_run)
    db.commit()
    db.refresh(test_run)
    return test_run


def update_test_run(db: Session, test_run_id: int, payload: TestRunUpdate) -> TestRun:
    test_run = _get_active_test_run(db, test_run_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(test_run, field, value)
    db.commit()
    db.refresh(test_run)
    return test_run


def delete_test_run(db: Session, test_run_id: int) -> None:
    test_run = _get_active_test_run(db, test_run_id)
    test_run.delete_time = datetime.now()
    db.commit()


def select_test_cases(db: Session, test_run_id: int, payload: SelectTestCasesRequest) -> list[TestRunCase]:
    _get_active_test_run(db, test_run_id)
    selected = []
    for test_case_id in payload.test_case_ids:
        existing = (
            db.query(TestRunCase)
            .filter(TestRunCase.test_run_id == test_run_id, TestRunCase.test_case_id == test_case_id)
            .first()
        )
        if existing:
            selected.append(existing)
            continue
        run_case = TestRunCase(test_run_id=test_run_id, test_case_id=test_case_id, tester_id=payload.tester_id)
        db.add(run_case)
        selected.append(run_case)
    db.commit()
    for item in selected:
        db.refresh(item)
    return selected


def update_test_run_case(db: Session, run_case_id: int, payload: TestRunCaseUpdate) -> TestRunCase:
    run_case = _get_test_run_case(db, run_case_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("result") and not data.get("execute_time"):
        run_case.execute_time = datetime.now()
    for field, value in data.items():
        setattr(run_case, field, value)
    db.commit()
    db.refresh(run_case)
    return run_case


def list_test_run_cases(db: Session) -> list[TestRunCase]:
    return db.query(TestRunCase).order_by(TestRunCase.id.desc()).all()


def _get_active_test_run(db: Session, test_run_id: int) -> TestRun:
    test_run = db.query(TestRun).filter(TestRun.id == test_run_id, TestRun.delete_time.is_(None)).first()
    if not test_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found")
    return test_run


def _get_test_run_case(db: Session, run_case_id: int) -> TestRunCase:
    run_case = db.query(TestRunCase).filter(TestRunCase.id == run_case_id).first()
    if not run_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run case not found")
    return run_case

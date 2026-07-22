from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.test_case import TestCase
from app.models.test_run import TestRun, TestRunCase
from app.services.lifecycle_service import iteration_lifecycle_phase, project_lifecycle_phase
from app.services.iteration_service import (
    ensure_iteration_mutable,
    iteration_scoped_project_ids,
    lock_iterations_for_mutation,
)
from app.services.project_team_service import default_test_run_owner_id
from app.services.task_service import linked_task_summaries
from app.views.test_run_view import SelectTestCasesRequest, TestRunCaseUpdate, TestRunCreate, TestRunUpdate


def list_test_runs(db: Session) -> list[TestRun]:
    test_runs = db.query(TestRun).filter(TestRun.deleted == 0).order_by(TestRun.id.desc()).all()
    for test_run in test_runs:
        test_run.linked_tasks = linked_task_summaries(db, "test_run", test_run.id)
    return test_runs


def create_test_run(db: Session, payload: TestRunCreate, actor_id: int | None = None) -> TestRun:
    data = payload.model_dump()
    _ensure_test_run_iteration_mutable_and_in_scope(
        db,
        iteration_project_ids={data.get("iteration_id"): data["project_id"]},
    )
    data["creator_id"] = actor_id
    data["lifecycle_phase"] = (
        iteration_lifecycle_phase(db, data.get("iteration_id"))
        or project_lifecycle_phase(db, data.get("project_id"))
    )
    if not data.get("test_owner_id"):
        data["test_owner_id"] = default_test_run_owner_id(db, data.get("project_id"))
    test_run = TestRun(**data)
    db.add(test_run)
    db.commit()
    db.refresh(test_run)
    return test_run


def update_test_run(db: Session, test_run_id: int, payload: TestRunUpdate) -> TestRun:
    original = _get_active_test_run(db, test_run_id)
    data = payload.model_dump(exclude_unset=True)
    target_iteration_id = data.get("iteration_id", original.iteration_id)
    _ensure_test_run_iteration_mutable_and_in_scope(
        db,
        iteration_project_ids={
            original.iteration_id: original.project_id,
            target_iteration_id: data.get("project_id", original.project_id),
        },
    )
    test_run = _get_active_test_run(db, test_run_id, for_update=True)
    for field, value in data.items():
        setattr(test_run, field, value)
    if "iteration_id" in data:
        test_run.lifecycle_phase = (
            iteration_lifecycle_phase(db, target_iteration_id)
            or project_lifecycle_phase(db, test_run.project_id)
        )
    db.commit()
    db.refresh(test_run)
    return test_run


def delete_test_run(db: Session, test_run_id: int) -> None:
    original = _get_active_test_run(db, test_run_id)
    _ensure_test_run_iteration_mutable_and_in_scope(
        db,
        iteration_project_ids={original.iteration_id: original.project_id},
    )
    test_run = _get_active_test_run(db, test_run_id, for_update=True)
    test_run.deleted = 1
    test_run.delete_time = datetime.now()
    db.commit()


def select_test_cases(db: Session, test_run_id: int, payload: SelectTestCasesRequest) -> list[TestRunCase]:
    test_run = _locked_mutable_test_run(db, test_run_id)
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
    _locked_mutable_test_run(db, run_case.test_run_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("result") and not data.get("execute_time"):
        run_case.execute_time = datetime.now()
    for field, value in data.items():
        setattr(run_case, field, value)
    if data.get("result"):
        test_case = db.query(TestCase).filter(TestCase.id == run_case.test_case_id, TestCase.deleted == 0).first()
        if test_case:
            test_case.last_execute_time = run_case.execute_time
            test_case.last_execute_result = run_case.result
    db.commit()
    db.refresh(run_case)
    return run_case


def list_test_run_cases(db: Session) -> list[TestRunCase]:
    return db.query(TestRunCase).order_by(TestRunCase.id.desc()).all()


def _get_active_test_run(db: Session, test_run_id: int, *, for_update: bool = False) -> TestRun:
    query = db.query(TestRun).filter(TestRun.id == test_run_id, TestRun.deleted == 0)
    if for_update:
        query = query.with_for_update()
    test_run = query.first()
    if not test_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found")
    return test_run


def _get_test_run_case(db: Session, run_case_id: int) -> TestRunCase:
    run_case = db.query(TestRunCase).filter(TestRunCase.id == run_case_id).first()
    if not run_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run case not found")
    return run_case


def _locked_mutable_test_run(db: Session, test_run_id: int) -> TestRun:
    original = _get_active_test_run(db, test_run_id)
    _ensure_test_run_iteration_mutable_and_in_scope(
        db,
        iteration_project_ids={original.iteration_id: original.project_id},
    )
    return _get_active_test_run(db, test_run_id, for_update=True)


def _ensure_test_run_iteration_mutable_and_in_scope(
    db: Session,
    *,
    iteration_project_ids: dict[int | None, int],
) -> None:
    locked_iterations = lock_iterations_for_mutation(db, set(iteration_project_ids))
    for iteration in locked_iterations.values():
        ensure_iteration_mutable(iteration)
        project_id = iteration_project_ids[iteration.id]
        if project_id not in iteration_scoped_project_ids(db, iteration.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Test run project is outside iteration scope",
            )

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.test_run import TestRun, TestRunCase
from app.services.current_handler_service import ensure_work_item_action
from app.services.business_component_service import (
    attach_work_item_components,
    replace_work_item_components,
    resolve_primary_component,
    work_item_component_ids,
)
from app.services.iteration_service import ensure_iteration_assignment_mutable
from app.services.project_permission_service import ensure_workflow_fields_not_updated, visible_project_ids
from app.services.lifecycle_service import (
    project_lifecycle_phase,
    requirement_lifecycle_phase,
    test_case_lifecycle_phase,
)
from app.services.iteration_assignment_service import (
    resolve_work_item_iteration,
    validate_requirement_iteration,
)
from app.services.status_operation_service import list_status_operations
from app.services.task_service import linked_task_summaries
from app.services.user_service import user_display_name
from app.services.work_item_iteration_history_service import list_iteration_history, move_work_item_to_iteration
from app.services.workflow_state_service import initial_work_item_workflow_values
from app.services.workflow_state_query_service import is_terminal_state
from app.views.bug_view import BugCreate, BugFromTestRunCaseRequest, BugUpdate


def list_bugs(db: Session, actor) -> list[Bug]:
    bugs = db.query(Bug).filter(
        Bug.deleted == 0, Bug.project_id.in_(visible_project_ids(db, actor))
    ).order_by(Bug.id.desc()).all()
    for bug in bugs:
        bug.linked_tasks = linked_task_summaries(db, "bug", bug.id)
        bug.iteration_history = list_iteration_history(db, "bug", bug.id)
        attach_work_item_components(db, "bug", bug)
    return bugs


def get_bug(db: Session, bug_id: int) -> Bug:
    bug = _get_active_bug(db, bug_id)
    bug.linked_tasks = linked_task_summaries(db, "bug", bug.id)
    bug.iteration_history = list_iteration_history(db, "bug", bug.id)
    attach_work_item_components(db, "bug", bug)
    return bug


def create_bug(db: Session, payload: BugCreate, actor_id: int | None = None) -> Bug:
    data = payload.model_dump()
    primary_component_id = data.pop("primary_component_id", None)
    related_component_ids = data.pop("related_component_ids", [])
    if primary_component_id is None and data.get("requirement_id"):
        primary_component_id, inherited_related_component_ids = work_item_component_ids(
            db, "requirement", data["requirement_id"]
        )
        if not related_component_ids:
            related_component_ids = inherited_related_component_ids
    requested_iteration_id = data.get("iteration_id")
    ensure_iteration_assignment_mutable(db, None, requested_iteration_id)
    data["iteration_id"] = validate_requirement_iteration(
        db,
        data["project_id"],
        requested_iteration_id,
    )
    data["creator_id"] = actor_id
    if data.get("iteration_id"):
        _ensure_iteration_can_accept_bug(db, data["iteration_id"], data.get("project_id"))
    data["lifecycle_phase"] = (
        requirement_lifecycle_phase(db, data.get("requirement_id"))
        or test_case_lifecycle_phase(db, data.get("test_case_id"))
        or project_lifecycle_phase(db, data.get("project_id"))
    )
    primary_component = resolve_primary_component(db, data["project_id"], primary_component_id)
    data.update(initial_work_item_workflow_values(
        db,
        "bug",
        data.get("project_id"),
        data.get("owner_id"),
        data.get("iteration_id"),
        primary_component_id,
    ))
    bug = Bug(**data)
    db.add(bug)
    db.flush()
    replace_work_item_components(
        db, "bug", bug.id, bug.project_id, primary_component_id, related_component_ids
    )
    if bug.iteration_id:
        move_work_item_to_iteration(db, bug, bug.iteration_id, actor_id=actor_id, reason="created")
    db.commit()
    db.refresh(bug)
    attach_work_item_components(db, "bug", bug)
    return bug


def create_bug_from_test_run_case(
    db: Session,
    run_case_id: int,
    payload: BugFromTestRunCaseRequest,
    actor_id: int | None = None,
) -> Bug:
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
    iteration_id = resolve_work_item_iteration(
        db,
        test_run.project_id,
        None,
        source_iteration_id=(
            requirement.iteration_id if requirement else (test_case.iteration_id or test_run.iteration_id)
        ),
        strict_source_iteration=True,
    )
    ensure_iteration_assignment_mutable(db, None, iteration_id)
    _ensure_iteration_can_accept_bug(db, iteration_id, test_run.project_id)
    owner_id = requirement.owner_id if requirement else None
    workflow_values = initial_work_item_workflow_values(
        db,
        "bug",
        test_run.project_id,
        owner_id,
        iteration_id,
    )
    bug = Bug(
        project_id=test_run.project_id,
        iteration_id=iteration_id,
        requirement_id=test_case.requirement_id,
        test_case_id=test_case.id,
        test_run_id=test_run.id,
        title=payload.title,
        severity=payload.severity,
        priority=payload.priority,
        owner_id=owner_id,
        proposer=payload.proposer or user_display_name(db, run_case.tester_id),
        reproduce_steps=payload.reproduce_steps,
        expected_result=payload.expected_result or test_case.expected_result,
        actual_result=payload.actual_result,
        **workflow_values,
        lifecycle_phase=test_case.lifecycle_phase,
        creator_id=actor_id,
    )
    db.add(bug)
    db.flush()
    move_work_item_to_iteration(
        db,
        bug,
        iteration_id,
        actor_id=actor_id,
        reason="test_run_bug_created",
    )
    db.commit()
    db.refresh(bug)
    return bug


def update_bug(db: Session, bug_id: int, payload: BugUpdate, actor_id: int | None = None) -> Bug:
    bug = _get_active_bug(db, bug_id)
    ensure_iteration_assignment_mutable(db, bug.iteration_id, bug.iteration_id)
    ensure_work_item_action(db, bug, actor_id, "Bug")
    ensure_workflow_fields_not_updated(payload.model_fields_set)
    data = payload.model_dump(exclude_unset=True)
    data.pop("status", None)
    data.pop("resolution", None)
    data.pop("verify_result", None)
    data.pop("close_reason", None)
    target_project_id = data.get("project_id", bug.project_id)
    source_relation_changed = "task_id" in data or "requirement_id" in data
    target_task_id = data.get("task_id", bug.task_id)
    target_requirement_id = data.get("requirement_id", bug.requirement_id)
    should_resolve_iteration = "iteration_id" in data or (
        source_relation_changed and (target_task_id is not None or target_requirement_id is not None)
    )
    if should_resolve_iteration:
        source_iteration_id = _bug_source_iteration_id(
            db,
            target_task_id,
            target_requirement_id,
        )
        data["iteration_id"] = resolve_work_item_iteration(
            db,
            target_project_id,
            data.get("iteration_id") if "iteration_id" in data else None,
            source_iteration_id=source_iteration_id,
        )
    target_iteration_id = data.get("iteration_id", bug.iteration_id)
    ensure_iteration_assignment_mutable(db, bug.iteration_id, target_iteration_id)
    if target_iteration_id:
        _ensure_iteration_can_accept_bug(db, target_iteration_id, target_project_id)
    if "iteration_id" in data:
        move_work_item_to_iteration(
            db,
            bug,
            data.pop("iteration_id"),
            actor_id=actor_id,
            reason="updated",
        )
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
    ensure_iteration_assignment_mutable(db, bug.iteration_id, bug.iteration_id)
    bug.deleted = 1
    bug.delete_time = datetime.now()
    db.commit()


def _get_active_bug(db: Session, bug_id: int) -> Bug:
    bug = db.query(Bug).filter(Bug.id == bug_id, Bug.deleted == 0).first()
    if not bug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bug not found")
    return bug


def _bug_source_iteration_id(
    db: Session, task_id: int | None, requirement_id: int | None
) -> int | None:
    if task_id:
        task = db.query(Task).filter(Task.id == task_id, Task.deleted == 0).first()
        if task:
            return task.iteration_id
    if requirement_id:
        requirement = db.query(Requirement).filter(
            Requirement.id == requirement_id, Requirement.deleted == 0
        ).first()
        if requirement:
            return requirement.iteration_id
    return None


def _ensure_iteration_can_accept_bug(db: Session, iteration_id: int, bug_project_id: int | None) -> None:
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    if not iteration:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Iteration not found")
    if is_terminal_state(iteration):
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

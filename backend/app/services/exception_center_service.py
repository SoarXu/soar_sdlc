from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.exception_rule import ExceptionRule
from app.models.requirement import Requirement
from app.models.iteration import Iteration
from app.models.iteration_completion_snapshot import IterationCompletionSnapshot
from app.models.project import Project
from app.models.status_operation import StatusOperationLog
from app.models.task import Task
from app.models.user import User
from app.models.project_member import ProjectMember
from app.models.role import Role, UserRole
from app.models.work_item_iteration_history import WorkItemIterationHistory
from app.models.workflow_definition import WorkflowTransition
from app.services.exception_rule_service import ensure_default_exception_rules
from app.services.workflow_state_query_service import (
    current_state_name,
    is_terminal_state,
    non_terminal_state_clause,
)


INTEGRITY_LABELS = {
    "owner_required_missing": "当前状态缺少处理人",
    "owner_ineligible": "当前处理人无执行资格",
    "iteration_history_inconsistent": "迭代归属审计链不完整",
    "missing_reactivation_audit": "Bug 重激活审计链不完整",
    "terminal_iteration_snapshot_mismatch": "终态迭代结束快照不一致",
}


@dataclass
class _ScanContext:
    rules: list[ExceptionRule]
    operations: dict[tuple[str, int], list[StatusOperationLog]]
    operations_by_id: dict[int, StatusOperationLog]
    histories: dict[tuple[str, int], list[WorkItemIterationHistory]]
    transitions: list[WorkflowTransition]
    users: dict[int, User]
    member_roles: dict[tuple[int, int], set[str]]
    global_roles: dict[int, set[str]]
    projects: dict[int, Project]
    snapshots: dict[int, IterationCompletionSnapshot]
    iterations: dict[int, Iteration]
    requirements_with_active_bugs: set[int]


def _scoped_items(db: Session, model, scoped_project_ids: set[int] | None) -> list:
    query = db.query(model).filter(model.deleted == 0)
    if scoped_project_ids is not None:
        query = query.filter(model.project_id.in_(scoped_project_ids))
    return query.all()


def _load_scan_context(
    db: Session,
    items_by_type: dict[str, list],
    scoped_project_ids: set[int] | None,
) -> _ScanContext:
    key_clauses = [
        (StatusOperationLog.object_type == object_type) & (StatusOperationLog.object_id.in_([item.id for item in items]))
        for object_type, items in items_by_type.items()
        if items
    ]
    operation_rows = db.query(StatusOperationLog).filter(or_(*key_clauses)).all() if key_clauses else []
    operations: dict[tuple[str, int], list[StatusOperationLog]] = defaultdict(list)
    for operation in operation_rows:
        operations[(operation.object_type, operation.object_id)].append(operation)
    for rows in operations.values():
        rows.sort(key=lambda row: (row.create_time or datetime.min, row.id))

    history_clauses = [
        (WorkItemIterationHistory.object_type == object_type)
        & (WorkItemIterationHistory.object_id.in_([item.id for item in items]))
        for object_type, items in items_by_type.items()
        if items
    ]
    history_rows = db.query(WorkItemIterationHistory).filter(or_(*history_clauses)).all() if history_clauses else []
    histories: dict[tuple[str, int], list[WorkItemIterationHistory]] = defaultdict(list)
    for history in history_rows:
        histories[(history.object_type, history.object_id)].append(history)
    for rows in histories.values():
        rows.sort(key=lambda row: (row.entered_at, row.id))

    all_items = [item for items in items_by_type.values() for item in items]
    definition_ids = {item.workflow_definition_id for item in all_items if item.workflow_definition_id}
    transitions = db.query(WorkflowTransition).filter(
        WorkflowTransition.definition_id.in_(definition_ids),
        WorkflowTransition.enabled.is_(True),
    ).all() if definition_ids else []

    project_ids = {item.project_id for item in all_items if item.project_id}
    owner_ids = {item.owner_id for item in all_items if item.owner_id}
    users = {
        user.id: user for user in db.query(User).filter(User.id.in_(owner_ids)).all()
    } if owner_ids else {}
    member_roles: dict[tuple[int, int], set[str]] = defaultdict(set)
    if project_ids and owner_ids:
        for member in db.query(ProjectMember).filter(
            ProjectMember.project_id.in_(project_ids),
            ProjectMember.user_id.in_(owner_ids),
        ).all():
            member_roles[(member.project_id, member.user_id)].add(member.project_role)
    global_roles: dict[int, set[str]] = defaultdict(set)
    if owner_ids:
        for user_id, role_key in db.query(UserRole.user_id, Role.role_key).join(
            Role, Role.id == UserRole.role_id
        ).filter(UserRole.user_id.in_(owner_ids), Role.enabled.is_(True)).all():
            global_roles[user_id].add(role_key)
    projects = {
        project.id: project for project in db.query(Project).filter(Project.id.in_(project_ids)).all()
    } if project_ids else {}

    iteration_ids = {
        iteration_id
        for iteration_id in [
            *(item.iteration_id for item in all_items),
            *(history.iteration_id for history in history_rows),
        ]
        if iteration_id
    }
    snapshots = {
        snapshot.iteration_id: snapshot
        for snapshot in db.query(IterationCompletionSnapshot).filter(
            IterationCompletionSnapshot.iteration_id.in_(iteration_ids)
        ).all()
    } if iteration_ids else {}
    iterations = {
        iteration.id: iteration
        for iteration in db.query(Iteration).filter(Iteration.id.in_(iteration_ids), Iteration.deleted == 0).all()
    } if iteration_ids else {}

    requirement_ids = {item.id for item in items_by_type.get("requirement", [])}
    active_bug_query = db.query(Bug.requirement_id).filter(
        Bug.requirement_id.in_(requirement_ids),
        Bug.deleted == 0,
        non_terminal_state_clause(Bug),
    )
    if scoped_project_ids is not None:
        active_bug_query = active_bug_query.filter(Bug.project_id.in_(scoped_project_ids))
    requirements_with_active_bugs = {
        requirement_id for (requirement_id,) in active_bug_query.distinct().all()
    } if requirement_ids else set()

    return _ScanContext(
        rules=db.query(ExceptionRule).filter(ExceptionRule.enabled.is_(True)).all(),
        operations=dict(operations),
        operations_by_id={operation.id: operation for operation in operation_rows},
        histories=dict(histories),
        transitions=transitions,
        users=users,
        member_roles=dict(member_roles),
        global_roles=dict(global_roles),
        projects=projects,
        snapshots=snapshots,
        iterations=iterations,
        requirements_with_active_bugs=requirements_with_active_bugs,
    )


def list_exception_refs(
    db: Session,
    scoped_project_ids: set[int] | None = None,
    *,
    now: datetime | None = None,
) -> list[dict]:
    if scoped_project_ids == set():
        return []
    ensure_default_exception_rules(db)
    items_by_type = {
        "requirement": _scoped_items(db, Requirement, scoped_project_ids),
        "task": _scoped_items(db, Task, scoped_project_ids),
        "bug": _scoped_items(db, Bug, scoped_project_ids),
    }
    context = _load_scan_context(db, items_by_type, scoped_project_ids)
    evaluation_time = now or datetime.now()
    refs: list[dict] = []
    seen: set[tuple[str, int, str]] = set()

    def add_if_due(
        object_type: str,
        item,
        exception_key: str,
        entered_at: datetime | None,
        *,
        current_count: int | None = None,
    ) -> None:
        signature = (object_type, item.id, exception_key)
        if signature in seen:
            return
        rule = _resolve_prefetched_rule(
            context.rules,
            exception_key,
            object_type,
            item.project_id,
            str(getattr(item, "priority", None) or getattr(item, "severity", None) or "") or None,
            getattr(item, "current_state_id", None),
            current_state_name(item),
        )
        if not rule:
            return
        if rule.threshold_count is not None and (current_count or 0) < rule.threshold_count:
            return
        elapsed_hours = _elapsed_hours(entered_at, evaluation_time)
        threshold_hours = rule.threshold_hours or 0
        if rule.threshold_hours is not None and elapsed_hours < threshold_hours:
            return
        seen.add(signature)
        refs.append(
            {
                "object_type": object_type,
                "id": item.id,
                "project_id": item.project_id,
                "priority": getattr(item, "priority", None) or getattr(item, "severity", None),
                "status": current_state_name(item),
                "owner_id": getattr(item, "owner_id", None),
                "handler_id": getattr(item, "owner_id", None),
                "exception_key": exception_key,
                "exception_label": rule.label,
                "entered_at": entered_at.isoformat() if entered_at else None,
                "threshold_hours": rule.threshold_hours,
                "threshold_count": rule.threshold_count,
                "overdue_hours": round(max(0.0, elapsed_hours - threshold_hours), 2),
            }
        )

    def add_integrity(object_type: str, item, exception_key: str, entered_at: datetime | None, detail: str) -> None:
        signature = (object_type, item.id, exception_key)
        if signature in seen:
            return
        seen.add(signature)
        refs.append({
            "object_type": object_type,
            "id": item.id,
            "project_id": item.project_id,
            "priority": getattr(item, "priority", None) or getattr(item, "severity", None),
            "status": current_state_name(item),
            "owner_id": getattr(item, "owner_id", None),
            "handler_id": getattr(item, "owner_id", None),
            "exception_key": exception_key,
            "exception_label": INTEGRITY_LABELS[exception_key],
            "exception_detail": detail,
            "entered_at": entered_at.isoformat() if entered_at else None,
            "overdue_hours": 0,
        })

    for requirement in items_by_type["requirement"]:
        entered_at = _latest_state_time_from_context(context, "requirement", requirement)
        if requirement.owner_id is None and not is_terminal_state(requirement):
            add_if_due("requirement", requirement, "unassigned_timeout", entered_at)
        elif requirement.owner_id and not is_terminal_state(requirement):
            add_if_due("requirement", requirement, "pending_timeout", entered_at)
        if _supports_entry_action(context, requirement, {"complete", "approve_confirmation"}):
            if requirement.id in context.requirements_with_active_bugs:
                add_if_due("requirement", requirement, "completed_requirement_active_bug", entered_at)
        _add_integrity_exceptions(context, add_integrity, "requirement", requirement, entered_at)

    for task in items_by_type["task"]:
        entered_at = _latest_state_time_from_context(context, "task", task)
        if task.owner_id is None and not is_terminal_state(task):
            add_if_due("task", task, "unassigned_timeout", entered_at)
        elif task.owner_id and not is_terminal_state(task):
            add_if_due("task", task, "pending_timeout", entered_at)
        if _supports_entry_action(context, task, {"claim", "assign", "return_rework"}):
            add_if_due("task", task, "fixing_timeout", entered_at)
        if _is_high_priority(task.priority) and not is_terminal_state(task):
            add_if_due("task", task, "high_priority_unprocessed", entered_at)
        _add_integrity_exceptions(context, add_integrity, "task", task, entered_at)

    for bug in items_by_type["bug"]:
        entered_at = _latest_state_time_from_context(context, "bug", bug)
        if bug.owner_id is None and not is_terminal_state(bug):
            add_if_due("bug", bug, "unassigned_timeout", entered_at)
        elif bug.owner_id and not is_terminal_state(bug):
            add_if_due("bug", bug, "pending_timeout", entered_at)
        if _supports_entry_action(context, bug, {"confirm_bug_type"}):
            add_if_due("bug", bug, "fixing_timeout", entered_at)
        if _supports_entry_action(context, bug, {"submit_verification"}):
            add_if_due("bug", bug, "pending_verification_timeout", entered_at)
        if _supports_entry_action(context, bug, {"verification_passed"}):
            add_if_due("bug", bug, "verified_not_closed", entered_at)
        if bug.verify_result == "failed":
            failed_at = _latest_action_time_from_context(context, "bug", bug.id, "verification_failed", bug.verify_time or entered_at)
            add_if_due("bug", bug, "verification_failed", failed_at)
        if (bug.reopen_count or 0) > 0:
            activated_at = _latest_action_time_from_context(context, "bug", bug.id, "activate", entered_at)
            add_if_due("bug", bug, "repeated_activation", activated_at, current_count=bug.reopen_count)
        if _is_high_priority(bug.priority or bug.severity) and not is_terminal_state(bug):
            add_if_due("bug", bug, "high_priority_unprocessed", entered_at)
        _add_integrity_exceptions(context, add_integrity, "bug", bug, entered_at)

    return refs


def _resolve_prefetched_rule(
    rules: list[ExceptionRule],
    exception_key: str,
    object_type: str,
    project_id: int | None,
    priority: str | None,
    current_state_id: int | None,
    _current_state_name: str | None = None,
) -> ExceptionRule | None:
    candidates = [
        item for item in rules
        if item.exception_key == exception_key
        and item.object_type in {"*", object_type}
        and item.project_id in {None, project_id}
        and item.priority in {None, priority}
        and item.status in {None, str(current_state_id) if current_state_id is not None else None}
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            int(item.project_id is not None),
            int(item.object_type == object_type),
            int(item.priority is not None),
            int(item.status is not None),
            -item.sort_order,
            item.id,
        ),
    )


def _latest_state_time_from_context(
    context: _ScanContext,
    object_type: str,
    item,
) -> datetime | None:
    matches = [
        operation for operation in context.operations.get((object_type, item.id), [])
        if operation.operation_kind == "state" and operation.to_state_id == item.current_state_id
    ]
    return max(matches, key=lambda row: (row.effective_time, row.id)).effective_time if matches else item.create_time


def _latest_action_time_from_context(
    context: _ScanContext,
    object_type: str,
    object_id: int,
    action: str,
    fallback: datetime | None,
) -> datetime | None:
    matches = [
        operation for operation in context.operations.get((object_type, object_id), [])
        if operation.operation_kind == "state" and operation.action == action
    ]
    return max(matches, key=lambda row: (row.effective_time, row.id)).effective_time if matches else fallback


def _supports_entry_action(context: _ScanContext, item, action_keys: set[str]) -> bool:
    return any(
        transition.definition_id == item.workflow_definition_id
        and transition.to_state_id == item.current_state_id
        and transition.action_key in action_keys
        for transition in context.transitions
    )


def _core_transitions(context: _ScanContext, item) -> list[WorkflowTransition]:
    return [
        transition for transition in context.transitions
        if transition.definition_id == item.workflow_definition_id
        and transition.from_state_id == item.current_state_id
        and not (transition.ui_config or {}).get("hidden")
        and not (transition.ui_config or {}).get("system_action")
        and (transition.ui_config or {}).get("action_category", "process") == "process"
        and (
            not (transition.condition_config or {}).get("task_types")
            or getattr(item, "task_type", None) in (transition.condition_config or {}).get("task_types")
        )
    ]


def _state_requires_owner_from_context(context: _ScanContext, item) -> bool:
    return any(
        (transition.ui_config or {}).get("requires_owner") is True
        or (transition.ui_config or {}).get("handler_scope") == "current_handler"
        for transition in _core_transitions(context, item)
    )


def _owner_is_eligible_from_context(context: _ScanContext, object_type: str, item) -> bool:
    owner = context.users.get(item.owner_id)
    member_roles = context.member_roles.get((item.project_id, item.owner_id), set())
    if not owner or owner.deleted != 0 or not owner.is_active or not member_roles:
        return False
    transitions = _core_transitions(context, item)
    if not transitions:
        return True
    identities = set(context.global_roles.get(owner.id, set())) | set(member_roles)
    identities.update({"current_handler", "owner", "project_member"})
    if getattr(item, "creator_id", None) == owner.id:
        identities.add("creator")
    if getattr(item, "reporter_id", None) == owner.id:
        identities.add("reporter")
    if getattr(item, "proposer_id", None) == owner.id:
        identities.add("proposer")
    project = context.projects.get(item.project_id)
    if (project and project.owner_id == owner.id) or "project_owner" in identities:
        identities.add("project_owner")
    if object_type == "bug" and getattr(item, "verified_by", None) == owner.id:
        identities.add("tester")

    for transition in transitions:
        ui_config = transition.ui_config or {}
        if ui_config.get("ownerless_only") is True:
            continue
        scope = ui_config.get("handler_scope")
        if scope not in {None, "allowed_identity", "project_member", "current_handler"}:
            continue
        allowed_roles = {role.strip() for role in (transition.allowed_roles or "").split(",") if role.strip()}
        if not allowed_roles or allowed_roles & identities:
            return True
    return False


def _latest_state_time(
    db: Session,
    object_type: str,
    object_id: int,
    current_state_id: int | None,
    fallback: datetime | None,
) -> datetime | None:
    operation = db.query(StatusOperationLog).filter(
        StatusOperationLog.object_type == object_type,
        StatusOperationLog.object_id == object_id,
        StatusOperationLog.to_state_id == current_state_id,
        StatusOperationLog.operation_kind == "state",
    ).order_by(StatusOperationLog.effective_time.desc(), StatusOperationLog.id.desc()).first()
    return operation.effective_time if operation else fallback


def _elapsed_hours(entered_at: datetime | None, now: datetime) -> float:
    if not entered_at:
        return 0.0
    evaluation_time = now
    if entered_at.tzinfo and not evaluation_time.tzinfo:
        evaluation_time = evaluation_time.replace(tzinfo=entered_at.tzinfo)
    elif evaluation_time.tzinfo and not entered_at.tzinfo:
        entered_at = entered_at.replace(tzinfo=evaluation_time.tzinfo)
    return max(0.0, (evaluation_time - entered_at).total_seconds() / 3600)


def _recorded_after(event_time: datetime, recorded_time: datetime) -> bool:
    return event_time.replace(microsecond=0) > recorded_time.replace(microsecond=0)


def _outside_record_window(event_time: datetime, recorded_time: datetime) -> bool:
    return event_time > recorded_time + timedelta(seconds=2)


def _history_recorded_time(
    context: _ScanContext,
    history: WorkItemIterationHistory,
    *,
    leaving: bool,
) -> datetime:
    operation = context.operations_by_id.get(history.operation_log_id) if history.operation_log_id else None
    if operation and operation.create_time:
        return operation.create_time
    return history.left_at if leaving and history.left_at else history.entered_at


def _is_high_priority(priority: str | None) -> bool:
    return str(priority or "").lower() in {"1", "high", "urgent"}


def _add_integrity_exceptions(context: _ScanContext, add_integrity, object_type: str, item, entered_at: datetime | None) -> None:
    if not is_terminal_state(item) and item.owner_id is None and _state_requires_owner_from_context(context, item):
        add_integrity(object_type, item, "owner_required_missing", entered_at, "当前工作流状态要求处理人，但 owner_id 为空")
    elif not is_terminal_state(item) and item.owner_id is not None and not _owner_is_eligible_from_context(context, object_type, item):
        add_integrity(object_type, item, "owner_ineligible", entered_at, "处理人账号、项目成员身份或当前动作资格无效")
    if _iteration_history_is_inconsistent_from_context(context, object_type, item):
        add_integrity(object_type, item, "iteration_history_inconsistent", entered_at, "当前归属、开放历史或转移操作记录不一致")
    if _terminal_snapshot_is_inconsistent_from_context(context, object_type, item):
        add_integrity(object_type, item, "terminal_iteration_snapshot_mismatch", entered_at, "事项不在结束快照内、结束后进入或当前事实与快照不一致")
    if object_type == "bug" and _bug_activation_audit_is_inconsistent_from_context(context, item):
        add_integrity("bug", item, "missing_reactivation_audit", entered_at, "activate 次数、原因或关联的离开/进入历史不完整")


def _iteration_history_is_inconsistent_from_context(context: _ScanContext, object_type: str, item) -> bool:
    rows = context.histories.get((object_type, item.id), [])
    open_rows = [row for row in rows if row.left_at is None]
    if item.iteration_id is None:
        if open_rows:
            return True
    elif len(open_rows) != 1 or open_rows[0].iteration_id != item.iteration_id:
        return True
    for index, row in enumerate(rows):
        if row.left_at is not None and (row.left_at < row.entered_at or not row.leave_reason):
            return True
        if index and rows[index - 1].left_at and rows[index - 1].left_at > row.entered_at:
            return True
    rows_requiring_operation = rows if len(rows) > 1 else [row for row in rows if row.left_at is not None]
    for row in rows_requiring_operation:
        operation = context.operations_by_id.get(row.operation_log_id) if row.operation_log_id else None
        if not operation or operation.object_type != object_type or operation.object_id != item.id:
            return True
        history_reasons = {row.enter_reason, row.leave_reason}
        expected_action = (
            "activate" if "reactivated" in history_reasons
            else "iteration_defer" if "deferred" in history_reasons
            else "iteration_unlink" if "unlinked" in history_reasons
            else "iteration_move" if history_reasons & {"updated", "iteration_project_scope_removed"}
            else None
        )
        expected_kind = "state" if expected_action == "activate" else "membership"
        if expected_action and (operation.action != expected_action or operation.operation_kind != expected_kind):
            return True
    return False


def _bug_activation_audit_is_inconsistent_from_context(context: _ScanContext, bug: Bug) -> bool:
    operations = context.operations.get(("bug", bug.id), [])
    activation_logs = [
        operation for operation in operations
        if operation.operation_kind == "state" and operation.action == "activate"
    ]
    verification_failure_logs = [
        operation for operation in operations
        if operation.operation_kind == "state" and operation.action == "verification_failed"
    ]
    if (bug.reopen_count or 0) != len(activation_logs) + len(verification_failure_logs):
        return True
    if not activation_logs:
        return False
    histories = context.histories.get(("bug", bug.id), [])
    for activation_index, operation in enumerate(activation_logs, start=1):
        selected = operation.selected_values if isinstance(operation.selected_values, dict) else {}
        if not (operation.reason or selected.get("reopen_reason")):
            return True
        operation_recorded_key = (operation.create_time or datetime.min, operation.id)
        failures_before_activation = sum(
            (failure.create_time or datetime.min, failure.id) <= operation_recorded_key
            for failure in verification_failure_logs
        )
        if _positive_int(selected.get("reopen_count_after")) != activation_index + failures_before_activation:
            return True
        linked = [row for row in histories if row.operation_log_id == operation.id]
        if not any(row.leave_reason == "reactivated" and row.left_at is not None for row in linked):
            return True
        if not any(row.enter_reason == "reactivated" for row in linked):
            return True
    return False


def _terminal_snapshot_is_inconsistent_from_context(context: _ScanContext, object_type: str, item) -> bool:
    histories = context.histories.get((object_type, item.id), [])
    for history in [row for row in histories if row.left_at is not None]:
        source_snapshot = context.snapshots.get(history.iteration_id)
        snapshot_recorded_at = source_snapshot.create_time if source_snapshot else None
        history_recorded_at = _history_recorded_time(context, history, leaving=True)
        if not source_snapshot or not snapshot_recorded_at or not _recorded_after(history_recorded_at, snapshot_recorded_at):
            continue
        if _is_valid_post_terminal_reactivation_from_context(context, object_type, item.id, history):
            continue
        return True

    if not item.iteration_id:
        return False
    iteration = context.iterations.get(item.iteration_id)
    if not iteration or not is_terminal_state(iteration):
        return False
    snapshot = context.snapshots.get(item.iteration_id)
    if not snapshot:
        return True
    snapshot_items = (snapshot.items or {}).get(object_type, [])
    snapshot_item = next((row for row in snapshot_items if row.get("id") == item.id), None)
    if not snapshot_item:
        return True
    open_history = next(
        (row for row in histories if row.iteration_id == item.iteration_id and row.left_at is None),
        None,
    )
    if open_history and snapshot.create_time and _recorded_after(
        _history_recorded_time(context, open_history, leaving=False),
        snapshot.create_time,
    ):
        return True
    return any((
        snapshot_item.get("state_id") != getattr(item, "current_state_id", None),
        snapshot_item.get("owner_id") != getattr(item, "owner_id", None),
    ))


def _is_valid_post_terminal_reactivation_from_context(
    context: _ScanContext,
    object_type: str,
    object_id: int,
    leave_history: WorkItemIterationHistory,
) -> bool:
    if object_type != "bug" or leave_history.leave_reason != "reactivated" or not leave_history.operation_log_id:
        return False
    operation = context.operations_by_id.get(leave_history.operation_log_id)
    if not operation or operation.operation_kind != "state" or operation.object_type != "bug":
        return False
    if operation.object_id != object_id or operation.action != "activate":
        return False
    selected = operation.selected_values if isinstance(operation.selected_values, dict) else {}
    source_iteration_id = _positive_int(selected.get("source_iteration_id"))
    target_iteration_id = _positive_int(selected.get("target_iteration_id"))
    if source_iteration_id != leave_history.iteration_id or target_iteration_id is None:
        return False
    if not operation.actor_id or not operation.reason or not selected.get("reopen_reason"):
        return False
    enter_history = next((
        row for row in context.histories.get(("bug", object_id), [])
        if row.iteration_id == target_iteration_id
        and row.enter_reason == "reactivated"
        and row.operation_log_id == operation.id
    ), None)
    if not enter_history or leave_history.left_by != operation.actor_id or enter_history.entered_by != operation.actor_id:
        return False
    if not leave_history.left_at or leave_history.left_at > enter_history.entered_at:
        return False
    if not operation.create_time or _outside_record_window(leave_history.left_at, operation.create_time):
        return False
    if _outside_record_window(enter_history.entered_at, operation.create_time):
        return False
    return True


def _is_valid_post_terminal_reactivation(
    db: Session,
    object_type: str,
    object_id: int,
    leave_history: WorkItemIterationHistory,
) -> bool:
    if object_type != "bug" or leave_history.leave_reason != "reactivated" or not leave_history.operation_log_id:
        return False
    operation = db.query(StatusOperationLog).filter(
        StatusOperationLog.id == leave_history.operation_log_id,
        StatusOperationLog.object_type == "bug",
        StatusOperationLog.object_id == object_id,
        StatusOperationLog.action == "activate",
        StatusOperationLog.operation_kind == "state",
    ).first()
    if not operation:
        return False
    selected = operation.selected_values if isinstance(operation.selected_values, dict) else {}
    source_iteration_id = _positive_int(selected.get("source_iteration_id"))
    target_iteration_id = _positive_int(selected.get("target_iteration_id"))
    if source_iteration_id is None or target_iteration_id is None:
        return False
    if source_iteration_id != leave_history.iteration_id:
        return False
    if not operation.actor_id or not operation.reason or not selected.get("reopen_reason"):
        return False
    enter_history = db.query(WorkItemIterationHistory).filter(
        WorkItemIterationHistory.object_type == "bug",
        WorkItemIterationHistory.object_id == object_id,
        WorkItemIterationHistory.iteration_id == target_iteration_id,
        WorkItemIterationHistory.enter_reason == "reactivated",
        WorkItemIterationHistory.operation_log_id == operation.id,
    ).first()
    if not enter_history:
        return False
    if leave_history.left_by != operation.actor_id or enter_history.entered_by != operation.actor_id:
        return False
    if not leave_history.left_at or leave_history.left_at > enter_history.entered_at:
        return False
    if not operation.create_time or _outside_record_window(leave_history.left_at, operation.create_time):
        return False
    if _outside_record_window(enter_history.entered_at, operation.create_time):
        return False
    return True


def _positive_int(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value

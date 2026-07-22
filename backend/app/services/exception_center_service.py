from datetime import datetime

from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.requirement import Requirement
from app.models.iteration import Iteration
from app.models.iteration_completion_snapshot import IterationCompletionSnapshot
from app.models.status_operation import StatusOperationLog
from app.models.task import Task
from app.models.user import User
from app.models.project_member import ProjectMember
from app.models.work_item_iteration_history import WorkItemIterationHistory
from app.services.exception_rule_service import ensure_default_exception_rules, resolve_exception_rule
from app.services.workflow_runtime_service import current_core_transitions, owner_has_executable_current_action
from app.services.workflow_state_query_service import (
    current_state_name,
    current_state_supports_entry_action,
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


def list_exception_refs(
    db: Session,
    scoped_project_ids: set[int] | None = None,
    *,
    now: datetime | None = None,
) -> list[dict]:
    ensure_default_exception_rules(db)
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
        rule = resolve_exception_rule(
            db,
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

    for requirement in db.query(Requirement).filter(Requirement.deleted == 0).all():
        if not _in_scope(requirement.project_id, scoped_project_ids):
            continue
        entered_at = _latest_state_time(db, "requirement", requirement.id, requirement.current_state_id, requirement.create_time)
        if requirement.owner_id is None and not is_terminal_state(requirement):
            add_if_due("requirement", requirement, "unassigned_timeout", entered_at)
        elif requirement.owner_id and not is_terminal_state(requirement):
            add_if_due("requirement", requirement, "pending_timeout", entered_at)
        if current_state_supports_entry_action(db, requirement, {"complete", "approve_confirmation"}):
            has_active_bug = db.query(Bug.id).filter(
                Bug.requirement_id == requirement.id,
                Bug.deleted == 0,
                non_terminal_state_clause(Bug),
            ).first()
            if has_active_bug:
                add_if_due("requirement", requirement, "completed_requirement_active_bug", entered_at)
        _add_integrity_exceptions(db, add_integrity, "requirement", requirement, entered_at)

    for task in db.query(Task).filter(Task.deleted == 0).all():
        if not _in_scope(task.project_id, scoped_project_ids):
            continue
        entered_at = _latest_state_time(db, "task", task.id, task.current_state_id, task.create_time)
        if task.owner_id is None and not is_terminal_state(task):
            add_if_due("task", task, "unassigned_timeout", entered_at)
        elif task.owner_id and not is_terminal_state(task):
            add_if_due("task", task, "pending_timeout", entered_at)
        if current_state_supports_entry_action(db, task, {"claim", "assign", "return_rework"}):
            add_if_due("task", task, "fixing_timeout", entered_at)
        if _is_high_priority(task.priority) and not is_terminal_state(task):
            add_if_due("task", task, "high_priority_unprocessed", entered_at)
        _add_integrity_exceptions(db, add_integrity, "task", task, entered_at)

    for bug in db.query(Bug).filter(Bug.deleted == 0).all():
        if not _in_scope(bug.project_id, scoped_project_ids):
            continue
        entered_at = _latest_state_time(db, "bug", bug.id, bug.current_state_id, bug.create_time)
        if bug.owner_id is None and not is_terminal_state(bug):
            add_if_due("bug", bug, "unassigned_timeout", entered_at)
        elif bug.owner_id and not is_terminal_state(bug):
            add_if_due("bug", bug, "pending_timeout", entered_at)
        if current_state_supports_entry_action(db, bug, {"confirm_bug_type"}):
            add_if_due("bug", bug, "fixing_timeout", entered_at)
        if current_state_supports_entry_action(db, bug, {"submit_verification"}):
            add_if_due("bug", bug, "pending_verification_timeout", entered_at)
        if current_state_supports_entry_action(db, bug, {"verification_passed"}):
            add_if_due("bug", bug, "verified_not_closed", entered_at)
        if bug.verify_result == "failed":
            failed_at = _latest_action_time(db, "bug", bug.id, "verification_failed", bug.verify_time or entered_at)
            add_if_due("bug", bug, "verification_failed", failed_at)
        if (bug.reopen_count or 0) > 0:
            activated_at = _latest_action_time(db, "bug", bug.id, "activate", entered_at)
            add_if_due("bug", bug, "repeated_activation", activated_at, current_count=bug.reopen_count)
        if _is_high_priority(bug.priority or bug.severity) and not is_terminal_state(bug):
            add_if_due("bug", bug, "high_priority_unprocessed", entered_at)
        _add_integrity_exceptions(db, add_integrity, "bug", bug, entered_at)

    return refs


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
        ~StatusOperationLog.action.like("iteration_%"),
    ).order_by(StatusOperationLog.effective_time.desc(), StatusOperationLog.id.desc()).first()
    return operation.effective_time if operation else fallback


def _latest_action_time(
    db: Session,
    object_type: str,
    object_id: int,
    action: str,
    fallback: datetime | None,
) -> datetime | None:
    operation = db.query(StatusOperationLog).filter(
        StatusOperationLog.object_type == object_type,
        StatusOperationLog.object_id == object_id,
        StatusOperationLog.action == action,
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


def _in_scope(project_id: int | None, scoped_project_ids: set[int] | None) -> bool:
    if scoped_project_ids is None:
        return True
    return bool(project_id and project_id in scoped_project_ids)


def _is_high_priority(priority: str | None) -> bool:
    return str(priority or "").lower() in {"1", "high", "urgent"}


def _add_integrity_exceptions(db: Session, add_integrity, object_type: str, item, entered_at: datetime | None) -> None:
    if not is_terminal_state(item) and item.owner_id is None and _state_requires_owner(db, item):
        add_integrity(object_type, item, "owner_required_missing", entered_at, "当前工作流状态要求处理人，但 owner_id 为空")
    elif not is_terminal_state(item) and item.owner_id is not None and not _owner_is_eligible(db, object_type, item):
        add_integrity(object_type, item, "owner_ineligible", entered_at, "处理人账号、项目成员身份或当前动作资格无效")
    if _iteration_history_is_inconsistent(db, object_type, item):
        add_integrity(object_type, item, "iteration_history_inconsistent", entered_at, "当前归属、开放历史或转移操作记录不一致")
    if _terminal_snapshot_is_inconsistent(db, object_type, item):
        add_integrity(object_type, item, "terminal_iteration_snapshot_mismatch", entered_at, "事项不在结束快照内、结束后进入或当前事实与快照不一致")
    if object_type == "bug" and _bug_activation_audit_is_inconsistent(db, item):
        add_integrity("bug", item, "missing_reactivation_audit", entered_at, "activate 次数、原因或关联的离开/进入历史不完整")


def _state_requires_owner(db: Session, item) -> bool:
    transitions = current_core_transitions(db, item)
    return any(
        (transition.ui_config or {}).get("requires_owner") is True
        or (transition.ui_config or {}).get("handler_scope") == "current_handler"
        for transition in transitions
    )


def _owner_is_eligible(db: Session, object_type: str, item) -> bool:
    user = db.query(User).filter(User.id == item.owner_id, User.deleted == 0, User.is_active.is_(True)).first()
    return bool(user and db.query(ProjectMember).filter(
        ProjectMember.project_id == item.project_id,
        ProjectMember.user_id == item.owner_id,
    ).first() and owner_has_executable_current_action(db, object_type, item, user))


def _iteration_history_is_inconsistent(db: Session, object_type: str, item) -> bool:
    rows = db.query(WorkItemIterationHistory).filter(
        WorkItemIterationHistory.object_type == object_type,
        WorkItemIterationHistory.object_id == item.id,
    ).order_by(WorkItemIterationHistory.entered_at.asc(), WorkItemIterationHistory.id.asc()).all()
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
    if rows_requiring_operation:
        for row in rows_requiring_operation:
            if row.operation_log_id is None:
                return True
            operation = db.query(StatusOperationLog).filter(
                StatusOperationLog.id == row.operation_log_id,
                StatusOperationLog.object_type == object_type,
                StatusOperationLog.object_id == item.id,
            ).first()
            if not operation:
                return True
            history_reasons = {row.enter_reason, row.leave_reason}
            expected_action = (
                "activate" if "reactivated" in history_reasons
                else "iteration_defer" if "deferred" in history_reasons
                else "iteration_unlink" if "unlinked" in history_reasons
                else "iteration_move" if history_reasons & {"updated", "iteration_project_scope_removed"}
                else None
            )
            if expected_action and operation.action != expected_action:
                return True
    return False


def _bug_activation_audit_is_inconsistent(db: Session, bug: Bug) -> bool:
    activation_logs = db.query(StatusOperationLog).filter(
        StatusOperationLog.object_type == "bug",
        StatusOperationLog.object_id == bug.id,
        StatusOperationLog.action == "activate",
    ).order_by(StatusOperationLog.effective_time.asc(), StatusOperationLog.id.asc()).all()
    verification_failure_logs = db.query(StatusOperationLog).filter(
        StatusOperationLog.object_type == "bug",
        StatusOperationLog.object_id == bug.id,
        StatusOperationLog.action == "verification_failed",
    ).all()
    if (bug.reopen_count or 0) != len(activation_logs) + len(verification_failure_logs):
        return True
    if not activation_logs:
        return False
    histories = db.query(WorkItemIterationHistory).filter(
        WorkItemIterationHistory.object_type == "bug",
        WorkItemIterationHistory.object_id == bug.id,
    ).all()
    for activation_index, operation in enumerate(activation_logs, start=1):
        selected = operation.selected_values if isinstance(operation.selected_values, dict) else {}
        if not (operation.reason or selected.get("reopen_reason")):
            return True
        failures_before_activation = sum(
            failure.effective_time <= operation.effective_time for failure in verification_failure_logs
        )
        if int(selected.get("reopen_count_after") or -1) != activation_index + failures_before_activation:
            return True
        linked = [row for row in histories if row.operation_log_id == operation.id]
        has_leave = any(row.leave_reason == "reactivated" and row.left_at is not None for row in linked)
        has_enter = any(row.enter_reason == "reactivated" for row in linked)
        if not has_leave or not has_enter:
            return True
    return False


def _terminal_snapshot_is_inconsistent(db: Session, object_type: str, item) -> bool:
    if not item.iteration_id:
        return False
    iteration = db.query(Iteration).filter(Iteration.id == item.iteration_id, Iteration.deleted == 0).first()
    if not iteration or not is_terminal_state(iteration):
        return False
    snapshot = db.query(IterationCompletionSnapshot).filter(
        IterationCompletionSnapshot.iteration_id == item.iteration_id
    ).first()
    if not snapshot:
        return True
    snapshot_items = (snapshot.items or {}).get(object_type, [])
    snapshot_item = next((row for row in snapshot_items if row.get("id") == item.id), None)
    if not snapshot_item:
        return True
    open_history = db.query(WorkItemIterationHistory).filter(
        WorkItemIterationHistory.object_type == object_type,
        WorkItemIterationHistory.object_id == item.id,
        WorkItemIterationHistory.iteration_id == item.iteration_id,
        WorkItemIterationHistory.left_at.is_(None),
    ).first()
    if open_history and open_history.entered_at > snapshot.ended_at:
        return True
    return any((
        snapshot_item.get("state_id") != getattr(item, "current_state_id", None),
        snapshot_item.get("owner_id") != getattr(item, "owner_id", None),
    ))

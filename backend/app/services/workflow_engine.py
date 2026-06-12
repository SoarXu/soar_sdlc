from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.requirement import Requirement
from app.models.status_operation import StatusOperationLog
from app.models.task import Task
from app.models.workflow_rule import WorkflowRule


@dataclass
class WorkflowExecutionResult:
    executed_rules: int = 0
    executed_actions: set[str] = field(default_factory=set)

    def mark_action(self, component_key: str) -> None:
        self.executed_actions.add(component_key)

    def has_action(self, component_key: str) -> bool:
        return component_key in self.executed_actions


@dataclass
class NodeResult:
    passed: bool = True


def execute_workflows(db: Session, target_object: str, trigger_action: str, context: dict[str, Any]) -> WorkflowExecutionResult:
    result = WorkflowExecutionResult()
    rules = (
        db.query(WorkflowRule)
        .filter(
            WorkflowRule.enabled == True,  # noqa: E712
            WorkflowRule.target_object == target_object,
            WorkflowRule.trigger_action == trigger_action,
        )
        .order_by(WorkflowRule.priority.asc(), WorkflowRule.id.asc())
        .all()
    )
    if not rules:
        return result

    for rule in rules:
        graph = _build_graph(rule.condition_json)
        trigger = _find_trigger(graph["nodes"])
        if not trigger or not _match_trigger(trigger, context):
            continue
        result.executed_rules += 1
        _run_children(db, graph, trigger["id"], context, result)
    return result


def _build_graph(condition_json: dict | list | None) -> dict[str, Any]:
    if not isinstance(condition_json, dict):
        return {"nodes": {}, "children": {}}
    nodes = {node["id"]: node for node in condition_json.get("nodes", []) if node.get("id")}
    children: dict[str, list[str]] = {}
    for edge in condition_json.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if source in nodes and target in nodes:
            children.setdefault(source, []).append(target)
    return {"nodes": nodes, "children": children}


def _find_trigger(nodes: dict[str, dict]) -> dict | None:
    return next((node for node in nodes.values() if node.get("category") == "trigger"), None)


def _match_trigger(node: dict, context: dict[str, Any]) -> bool:
    config = node.get("config") or {}
    from_status = config.get("from_status")
    to_status = config.get("to_status")
    if from_status and from_status != "*" and from_status != context.get("from_status"):
        return False
    if to_status and to_status != context.get("to_status"):
        return False
    result_in = config.get("result_in")
    if result_in and context.get("result") not in result_in:
        return False
    return True


def _run_children(db: Session, graph: dict[str, Any], node_id: str, context: dict[str, Any], result: WorkflowExecutionResult) -> None:
    for child_id in graph["children"].get(node_id, []):
        node = graph["nodes"].get(child_id)
        if not node:
            continue
        node_result = _run_node(db, node, context, result)
        if node_result.passed:
            _run_children(db, graph, child_id, context, result)


def _run_node(db: Session, node: dict, context: dict[str, Any], result: WorkflowExecutionResult) -> NodeResult:
    handler = NODE_HANDLERS.get(node.get("component_key"))
    if not handler:
        return NodeResult(passed=True)
    node_result = handler(db, node, context, result)
    if node.get("category") == "action":
        result.mark_action(node.get("component_key"))
    return node_result


def _handle_status_matches(db: Session, node: dict, context: dict[str, Any], result: WorkflowExecutionResult) -> NodeResult:
    status_in = set((node.get("config") or {}).get("status_in") or [])
    if not status_in:
        return NodeResult(passed=True)
    return NodeResult(passed=context.get("to_status") in status_in or context.get("current_status") in status_in)


def _handle_child_unclosed_exists(db: Session, node: dict, context: dict[str, Any], result: WorkflowExecutionResult) -> NodeResult:
    config = node.get("config") or {}
    child_object = config.get("child_object")
    status_not_in = config.get("status_not_in") or ["closed"]
    if context.get("target_object") == "project" and child_object == "requirement":
        exists = (
            db.query(Requirement.id)
            .filter(
                Requirement.project_id == context["object_id"],
                Requirement.deleted == 0,
                Requirement.status.notin_(status_not_in),
            )
            .first()
            is not None
        )
        return NodeResult(passed=exists)
    if context.get("target_object") == "project" and child_object == "task":
        exists = (
            db.query(Task.id)
            .filter(
                Task.project_id == context["object_id"],
                Task.deleted == 0,
                Task.status.notin_(status_not_in),
            )
            .first()
            is not None
        )
        return NodeResult(passed=exists)
    return NodeResult(passed=False)


def _handle_field_required(db: Session, node: dict, context: dict[str, Any], result: WorkflowExecutionResult) -> NodeResult:
    field_key = (node.get("config") or {}).get("field_key")
    return NodeResult(passed=bool(context.get(field_key)) if field_key else True)


def _handle_block_operation(db: Session, node: dict, context: dict[str, Any], result: WorkflowExecutionResult) -> NodeResult:
    message = (node.get("config") or {}).get("message") or "当前操作被工作流规则阻断"
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _handle_batch_change_child_status(db: Session, node: dict, context: dict[str, Any], result: WorkflowExecutionResult) -> NodeResult:
    config = node.get("config") or {}
    child_object = config.get("child_object")
    target_status = config.get("target_status")
    if not target_status:
        return NodeResult(passed=False)
    if context.get("target_object") == "project" and child_object == "requirement":
        _batch_change_project_requirements(db, context, target_status, config)
        return NodeResult(passed=True)
    if context.get("target_object") == "project" and child_object == "task":
        _batch_change_project_tasks(db, context, target_status, config)
        return NodeResult(passed=True)
    return NodeResult(passed=False)


def _batch_change_project_requirements(db: Session, context: dict[str, Any], target_status: str, config: dict[str, Any]) -> None:
    if target_status != "closed":
        return
    requirement_rows = (
        db.query(Requirement.id, Requirement.status)
        .filter(
            Requirement.project_id == context["object_id"],
            Requirement.deleted == 0,
            Requirement.status != "closed",
        )
        .all()
    )
    if not requirement_rows:
        return
    requirement_ids = [row.id for row in requirement_rows]
    reason = config.get("reason") or context.get("reason")
    remark = context.get("remark")
    now = datetime.now()
    db.query(Requirement).filter(Requirement.id.in_(requirement_ids)).update(
        {Requirement.status: "closed"},
        synchronize_session=False,
    )
    db.add_all(
        StatusOperationLog(
            object_type="requirement",
            object_id=row.id,
            action="close",
            from_status=row.status,
            to_status="closed",
            reason=reason,
            effective_time=context.get("effective_time") or now,
            remark=remark,
            actor_id=context.get("operator_id"),
        )
        for row in requirement_rows
    )


def _batch_change_project_tasks(db: Session, context: dict[str, Any], target_status: str, config: dict[str, Any]) -> None:
    if target_status != "closed":
        return
    task_rows = (
        db.query(Task.id, Task.status)
        .filter(
            Task.project_id == context["object_id"],
            Task.deleted == 0,
            Task.status != "closed",
        )
        .all()
    )
    if not task_rows:
        return
    task_ids = [row.id for row in task_rows]
    reason = config.get("reason") or context.get("reason")
    remark = context.get("remark")
    now = datetime.now()
    db.query(Task).filter(Task.id.in_(task_ids)).update(
        {Task.status: "closed"},
        synchronize_session=False,
    )
    db.add_all(
        StatusOperationLog(
            object_type="task",
            object_id=row.id,
            action="close",
            from_status=row.status,
            to_status="closed",
            reason=reason,
            effective_time=context.get("effective_time") or now,
            remark=remark,
            actor_id=context.get("operator_id"),
        )
        for row in task_rows
    )


def _handle_write_history(db: Session, node: dict, context: dict[str, Any], result: WorkflowExecutionResult) -> NodeResult:
    project = db.query(Project).filter(Project.id == context["object_id"], Project.deleted == 0).first()
    if not project:
        return NodeResult(passed=False)
    remark_template = (node.get("config") or {}).get("remark")
    db.add(
        StatusOperationLog(
            object_type="project",
            object_id=project.id,
            action="workflow",
            from_status=context.get("from_status"),
            to_status=context.get("to_status"),
            reason=context.get("reason"),
            effective_time=context.get("effective_time") or datetime.now(),
            remark=remark_template or context.get("remark"),
            actor_id=context.get("operator_id"),
        )
    )
    return NodeResult(passed=True)


NODE_HANDLERS = {
    "status_matches": _handle_status_matches,
    "child_unclosed_exists": _handle_child_unclosed_exists,
    "field_required": _handle_field_required,
    "batch_change_child_status": _handle_batch_change_child_status,
    "block_operation": _handle_block_operation,
    "write_history": _handle_write_history,
}

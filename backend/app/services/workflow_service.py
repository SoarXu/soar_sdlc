from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.workflow_rule import WorkflowRule
from app.services.workflow_catalog import STATUS_OPTIONS
from app.services.workflow_component_service import list_designer_components
from app.views.workflow_view import WorkflowRuleCreate, WorkflowRuleUpdate


def list_workflow_rules(db: Session) -> list[WorkflowRule]:
    return db.query(WorkflowRule).order_by(WorkflowRule.priority.asc(), WorkflowRule.id.desc()).all()


def create_workflow_rule(db: Session, payload: WorkflowRuleCreate) -> WorkflowRule:
    rule = WorkflowRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_workflow_rule(db: Session, rule_id: int, payload: WorkflowRuleUpdate) -> WorkflowRule:
    rule = _get_workflow_rule(db, rule_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


def delete_workflow_rule(db: Session, rule_id: int) -> None:
    rule = _get_workflow_rule(db, rule_id)
    db.delete(rule)
    db.commit()


def list_workflow_components(db: Session) -> list[dict]:
    return list_designer_components(db)


def list_workflow_templates() -> list[dict]:
    return [
        _project_close_requirements_template(),
        _requirement_activate_tasks_template(),
        _test_case_failed_bug_template(),
        _bug_fixed_notify_template(),
        _iteration_finish_guard_template(),
    ]


def _get_workflow_rule(db: Session, rule_id: int) -> WorkflowRule:
    rule = db.query(WorkflowRule).filter(WorkflowRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow rule not found")
    return rule


def _project_close_requirements_template() -> dict:
    nodes = [
        _node("node-1", "project_status_changed", "trigger", "项目关闭", 80, 80, {"to_status": "closed"}),
        _node("node-2", "child_unclosed_exists", "condition", "存在未关闭需求", 340, 80, {"child_object": "requirement", "status_not_in": ["closed"]}),
        _node("node-3", "batch_change_child_status", "action", "关闭未关闭需求", 600, 80, {"child_object": "requirement", "target_status": "closed", "reason": "不做"}),
        _node("node-4", "batch_change_child_status", "action", "关闭需求关联任务", 860, 80, {"child_object": "task", "target_status": "closed", "reason": "不做"}),
    ]
    return _template(
        "project_close_requirements",
        "项目关闭后关闭未关闭需求",
        "project",
        "status_changed",
        "项目关闭触发项目中未关闭需求和关联任务关闭。",
        nodes,
        _edges(["node-1", "node-2", "node-3", "node-4"]),
    )


def _requirement_activate_tasks_template() -> dict:
    nodes = [
        _node("node-1", "requirement_status_changed", "trigger", "需求激活", 80, 80, {"to_status": "active"}),
        _node("node-2", "batch_change_child_status", "action", "任务进入进行中", 340, 80, {"child_object": "task", "target_status": "doing"}),
    ]
    return _template("requirement_activate_tasks", "需求激活后任务进行中", "requirement", "status_changed", "需求激活后带动关联任务进入进行中。", nodes, _edges(["node-1", "node-2"]))


def _test_case_failed_bug_template() -> dict:
    nodes = [
        _node("node-1", "test_case_result_changed", "trigger", "用例失败或阻塞", 80, 80, {"result_in": ["failed", "blocked"]}),
        _node("node-2", "create_bug", "action", "允许创建 Bug", 340, 80, {"bug_type": "代码错误"}),
    ]
    return _template("test_case_failed_bug", "用例失败后提 Bug", "test_case", "execution_result_changed", "失败或阻塞用例允许提 Bug。", nodes, _edges(["node-1", "node-2"]))


def _bug_fixed_notify_template() -> dict:
    nodes = [
        _node("node-1", "bug_status_changed", "trigger", "Bug 待验证", 80, 80, {"to_status": "verifying"}),
        _node("node-2", "send_notification", "action", "通知测试验证", 340, 80, {"receiver": "tester"}),
    ]
    return _template("bug_fixed_notify", "Bug 修复完成通知验证", "bug", "status_changed", "Bug 进入待验证后通知测试人员。", nodes, _edges(["node-1", "node-2"]))


def _iteration_finish_guard_template() -> dict:
    nodes = [
        _node("node-1", "iteration_status_changed", "trigger", "迭代完成", 80, 80, {"to_status": "finished"}),
        _node("node-2", "child_unclosed_exists", "condition", "存在未关闭需求", 340, 80, {"child_object": "requirement", "status_not_in": ["closed", "done"]}),
        _node("node-3", "block_operation", "action", "阻断完成", 600, 80, {"message": "迭代下存在未完成需求"}),
    ]
    return _template("iteration_finish_guard", "迭代完成前校验需求", "iteration", "status_changed", "迭代完成前检查需求是否全部完成或关闭。", nodes, _edges(["node-1", "node-2", "node-3"]))


def _node(node_id: str, component_key: str, category: str, label: str, x: int, y: int, config: dict) -> dict:
    return {"id": node_id, "component_key": component_key, "category": category, "label": label, "x": x, "y": y, "config": config}


def _edges(node_ids: list[str]) -> list[dict]:
    return [{"id": f"edge-{index + 1}", "source": node_ids[index], "target": node_ids[index + 1]} for index in range(len(node_ids) - 1)]


def _template(template_key: str, template_name: str, target_object: str, trigger_action: str, description: str, nodes: list[dict], edges: list[dict]) -> dict:
    condition_json = {"designer_version": 1, "nodes": nodes, "edges": edges}
    action_json = {
        "trigger": {"target_object": target_object, "trigger_action": trigger_action, "config": nodes[0]["config"] if nodes else {}},
        "steps": [{"type": node["category"], "component_key": node["component_key"], "config": node["config"]} for node in nodes[1:]],
    }
    return {
        "template_key": template_key,
        "template_name": template_name,
        "target_object": target_object,
        "trigger_action": trigger_action,
        "description": description,
        "condition_json": condition_json,
        "action_json": action_json,
    }

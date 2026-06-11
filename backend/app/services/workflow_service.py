from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.workflow_rule import WorkflowRule
from app.views.workflow_view import WorkflowRuleCreate, WorkflowRuleUpdate


STATUS_OPTIONS = [
    {"label": "规划中", "value": "planning"},
    {"label": "进行中", "value": "active"},
    {"label": "已挂起", "value": "paused"},
    {"label": "已关闭", "value": "closed"},
    {"label": "草稿", "value": "draft"},
    {"label": "待办", "value": "todo"},
    {"label": "修复中", "value": "fixing"},
    {"label": "待验证", "value": "verifying"},
]


def _object_options() -> list[dict[str, str]]:
    return [
        {"label": "项目", "value": "project"},
        {"label": "项目集", "value": "program"},
        {"label": "迭代", "value": "iteration"},
        {"label": "需求", "value": "requirement"},
        {"label": "任务", "value": "task"},
        {"label": "Bug", "value": "bug"},
        {"label": "测试用例", "value": "test_case"},
    ]


WORKFLOW_COMPONENTS = [
    {
        "component_key": "project_status_changed",
        "category": "trigger",
        "label": "项目状态变更",
        "description": "当项目从一个状态流转到另一个状态时触发。",
        "config_schema": [
            {"field": "from_status", "label": "来源状态", "type": "select", "options": STATUS_OPTIONS, "allow_any": True},
            {"field": "to_status", "label": "目标状态", "type": "select", "options": STATUS_OPTIONS},
        ],
    },
    {
        "component_key": "program_status_changed",
        "category": "trigger",
        "label": "项目集状态变更",
        "description": "当项目集状态变化时触发。",
        "config_schema": [
            {"field": "to_status", "label": "目标状态", "type": "select", "options": STATUS_OPTIONS},
        ],
    },
    {
        "component_key": "iteration_status_changed",
        "category": "trigger",
        "label": "迭代状态变更",
        "description": "当迭代状态变化时触发。",
        "config_schema": [
            {"field": "to_status", "label": "目标状态", "type": "select", "options": STATUS_OPTIONS},
        ],
    },
    {
        "component_key": "requirement_status_changed",
        "category": "trigger",
        "label": "需求状态变更",
        "description": "当需求状态变化时触发。",
        "config_schema": [
            {"field": "to_status", "label": "目标状态", "type": "select", "options": STATUS_OPTIONS},
        ],
    },
    {
        "component_key": "task_status_changed",
        "category": "trigger",
        "label": "任务状态变更",
        "description": "当任务状态变化时触发。",
        "config_schema": [
            {"field": "to_status", "label": "目标状态", "type": "select", "options": STATUS_OPTIONS},
        ],
    },
    {
        "component_key": "bug_status_changed",
        "category": "trigger",
        "label": "Bug 状态变更",
        "description": "当 Bug 状态变化时触发。",
        "config_schema": [
            {"field": "to_status", "label": "目标状态", "type": "select", "options": STATUS_OPTIONS},
        ],
    },
    {
        "component_key": "test_case_result_changed",
        "category": "trigger",
        "label": "用例执行结果",
        "description": "当测试用例执行结果为失败或阻塞时触发。",
        "config_schema": [
            {
                "field": "result_in",
                "label": "执行结果",
                "type": "multi_select",
                "options": [{"label": "失败", "value": "failed"}, {"label": "阻塞", "value": "blocked"}],
            },
        ],
    },
    {
        "component_key": "field_changed",
        "category": "trigger",
        "label": "字段变更",
        "description": "当负责人、状态等字段变化时触发。",
        "config_schema": [{"field": "field_key", "label": "字段标识", "type": "text"}],
    },
    {
        "component_key": "status_matches",
        "category": "condition",
        "label": "状态匹配",
        "description": "判断当前对象状态是否满足条件。",
        "config_schema": [{"field": "status_in", "label": "状态范围", "type": "multi_select", "options": STATUS_OPTIONS}],
    },
    {
        "component_key": "child_unclosed_exists",
        "category": "condition",
        "label": "存在未关闭子对象",
        "description": "判断项目、需求等对象下是否存在未关闭子对象。",
        "config_schema": [
            {"field": "child_object", "label": "子对象", "type": "select", "options": _object_options()},
            {"field": "status_not_in", "label": "排除状态", "type": "multi_select", "options": STATUS_OPTIONS},
        ],
    },
    {
        "component_key": "field_required",
        "category": "condition",
        "label": "字段必填",
        "description": "校验日期、原因、负责人等字段必填。",
        "config_schema": [{"field": "field_key", "label": "字段标识", "type": "text"}],
    },
    {
        "component_key": "role_matches",
        "category": "condition",
        "label": "角色匹配",
        "description": "限制只有特定角色可以执行后续动作。",
        "config_schema": [{"field": "role_key", "label": "角色标识", "type": "text"}],
    },
    {
        "component_key": "change_current_status",
        "category": "action",
        "label": "修改当前对象状态",
        "description": "将当前对象状态修改为指定结果。",
        "config_schema": [{"field": "target_status", "label": "目标状态", "type": "select", "options": STATUS_OPTIONS}],
    },
    {
        "component_key": "batch_change_child_status",
        "category": "action",
        "label": "批量修改子对象状态",
        "description": "批量修改子对象状态，例如关闭项目下未关闭需求。",
        "config_schema": [
            {"field": "child_object", "label": "子对象", "type": "select", "options": _object_options()},
            {"field": "target_status", "label": "目标状态", "type": "select", "options": STATUS_OPTIONS},
            {"field": "reason", "label": "原因", "type": "text"},
        ],
    },
    {
        "component_key": "assign_owner",
        "category": "action",
        "label": "设置负责人",
        "description": "按项目负责人、需求负责人等规则设置负责人。",
        "config_schema": [{"field": "owner_source", "label": "负责人来源", "type": "text"}],
    },
    {
        "component_key": "create_bug",
        "category": "action",
        "label": "创建 Bug",
        "description": "根据用例执行结果创建 Bug。",
        "config_schema": [{"field": "bug_type", "label": "Bug 类型", "type": "text"}],
    },
    {
        "component_key": "send_notification",
        "category": "action",
        "label": "发送通知",
        "description": "通知负责人、测试人员或项目负责人。",
        "config_schema": [{"field": "receiver", "label": "接收人", "type": "text"}],
    },
    {
        "component_key": "block_operation",
        "category": "action",
        "label": "阻断操作",
        "description": "不满足规则时阻断当前操作并展示提示。",
        "config_schema": [{"field": "message", "label": "提示语", "type": "textarea"}],
    },
    {
        "component_key": "write_history",
        "category": "action",
        "label": "写入操作历史",
        "description": "记录状态变化、批量动作和执行备注。",
        "config_schema": [{"field": "remark", "label": "备注模板", "type": "textarea"}],
    },
]


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


def list_workflow_components() -> list[dict]:
    return WORKFLOW_COMPONENTS


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

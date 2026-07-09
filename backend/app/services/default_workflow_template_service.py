from datetime import datetime

from sqlalchemy.orm import Session

from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.views.workflow_definition_view import WorkflowGraphSave, WorkflowStateBase, WorkflowTransitionBase


def ensure_default_workflow_templates(db: Session) -> list[WorkflowDefinition]:
    definitions: list[WorkflowDefinition] = []
    for spec in _default_template_specs():
        definition = (
            db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.scope_type == "system",
                WorkflowDefinition.object_type == spec["object_type"],
                WorkflowDefinition.template_key == spec["template_key"],
            )
            .first()
        )
        if not definition:
            definition = WorkflowDefinition(
                name=spec["name"],
                object_type=spec["object_type"],
                scope_type="system",
                scope_id=None,
                template_key=spec["template_key"],
                parent_definition_id=None,
                is_default_template=True,
                enabled=True,
                version=1,
            )
            db.add(definition)
            db.flush()
            _replace_graph(db, definition.id, spec["graph"])
        else:
            changed = False
            if definition.name != spec["name"]:
                definition.name = spec["name"]
                changed = True
            if definition.template_key != spec["template_key"]:
                definition.template_key = spec["template_key"]
                changed = True
            if definition.is_default_template is not True:
                definition.is_default_template = True
                changed = True
            if definition.scope_type != "system" or definition.scope_id is not None:
                definition.scope_type = "system"
                definition.scope_id = None
                changed = True
            if not _graph_matches(db, definition.id, spec["graph"]):
                _replace_graph(db, definition.id, spec["graph"])
                definition.version = (definition.version or 1) + 1
                changed = True
            if changed:
                definition.update_time = datetime.now()
        definitions.append(definition)
    db.commit()
    for definition in definitions:
        db.refresh(definition)
    return definitions


def graph_for_object_type(object_type: str) -> WorkflowGraphSave:
    for spec in _default_template_specs():
        if spec["object_type"] == object_type:
            return spec["graph"]
    raise KeyError(object_type)


def default_template_summaries() -> list[dict]:
    return [
        {
            "template_key": spec["template_key"],
            "template_name": spec["name"],
            "target_object": spec["object_type"],
            "trigger_action": "status_transition",
            "description": spec["description"],
            "condition_json": {},
            "action_json": {
                "states": [state.model_dump() for state in spec["graph"].states],
                "transitions": [transition.model_dump() for transition in spec["graph"].transitions],
            },
        }
        for spec in _default_template_specs()
    ]


def _graph_matches(db: Session, definition_id: int, graph: WorkflowGraphSave) -> bool:
    current_states = (
        db.query(WorkflowState)
        .filter(WorkflowState.definition_id == definition_id)
        .order_by(WorkflowState.sort_order.asc(), WorkflowState.id.asc())
        .all()
    )
    current_transitions = (
        db.query(WorkflowTransition)
        .filter(WorkflowTransition.definition_id == definition_id)
        .order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc())
        .all()
    )
    if len(current_states) != len(graph.states) or len(current_transitions) != len(graph.transitions):
        return False
    state_signature = [
        (item.status_key, item.status_name, item.category, item.color, item.x, item.y, item.sort_order, item.enabled)
        for item in current_states
    ]
    target_state_signature = [
        (item.status_key, item.status_name, item.category, item.color, item.x, item.y, item.sort_order, item.enabled)
        for item in graph.states
    ]
    transition_signature = [
        (
            item.action_key,
            item.action_name,
            item.from_status,
            item.to_status,
            item.allowed_roles,
            item.handler_rule,
            item.condition_config,
            item.validator_config,
            item.ui_config,
            item.form_config,
            item.enabled,
            item.sort_order,
        )
        for item in current_transitions
    ]
    target_transition_signature = [
        (
            item.action_key,
            item.action_name,
            item.from_status,
            item.to_status,
            item.allowed_roles,
            item.handler_rule,
            item.condition_config,
            item.validator_config,
            item.ui_config,
            item.form_config,
            item.enabled,
            item.sort_order,
        )
        for item in graph.transitions
    ]
    return state_signature == target_state_signature and transition_signature == target_transition_signature


def _replace_graph(db: Session, definition_id: int, graph: WorkflowGraphSave) -> None:
    db.query(WorkflowTransition).filter(WorkflowTransition.definition_id == definition_id).delete(synchronize_session=False)
    db.query(WorkflowState).filter(WorkflowState.definition_id == definition_id).delete(synchronize_session=False)
    for state in graph.states:
        db.add(WorkflowState(definition_id=definition_id, **state.model_dump()))
    for transition in graph.transitions:
        db.add(WorkflowTransition(definition_id=definition_id, **transition.model_dump()))


def _default_template_specs() -> list[dict]:
    return [
        {
            "template_key": "requirement.default",
            "object_type": "requirement",
            "name": "默认需求工作流模板",
            "description": "系统内置的需求默认工作流模板。",
            "graph": _requirement_graph(),
        },
        {
            "template_key": "task.default",
            "object_type": "task",
            "name": "默认任务工作流模板",
            "description": "系统内置的任务默认工作流模板。",
            "graph": _task_graph(),
        },
        {
            "template_key": "bug.default",
            "object_type": "bug",
            "name": "默认缺陷工作流模板",
            "description": "系统内置的缺陷默认工作流模板。",
            "graph": _bug_graph(),
        },
        {
            "template_key": "iteration.default",
            "object_type": "iteration",
            "name": "默认迭代工作流模板",
            "description": "系统内置的迭代默认工作流模板。",
            "graph": _iteration_graph(),
        },
        {
            "template_key": "project.default",
            "object_type": "project",
            "name": "默认项目工作流模板",
            "description": "系统内置的项目默认工作流模板。",
            "graph": _project_graph(),
        },
    ]


def _requirement_graph() -> WorkflowGraphSave:
    return WorkflowGraphSave(
        states=[
            _state("pending_assignment", "待分派", "start", "#6b7280", 80, 100),
            _state("in_processing", "处理中", "normal", "#2563eb", 280, 100),
            _state("pending_confirmation", "待确认", "normal", "#7c3aed", 480, 100),
            _state("completed", "已完成", "terminal", "#059669", 680, 100),
            _state("canceled", "已取消", "terminal", "#94a3b8", 480, 240),
        ],
        transitions=[
            _transition("claim", "认领", "pending_assignment", "in_processing", target_type="actor"),
            _transition("assign", "指派", "pending_assignment", "in_processing", target_type="explicit_owner"),
            _transition(
                "complete",
                "完成",
                "in_processing",
                "completed",
                target_type="keep_current",
                validator_config={"type": "requirement_terminal_gate", "block_on_open_bugs": True, "block_on_open_tasks": True},
                ui_config={"list_display": "primary", "list_priority": 10},
            ),
            _transition(
                "cancel",
                "取消",
                "pending_assignment",
                "canceled",
                target_type="keep_current",
                validator_config={"type": "requirement_terminal_gate", "block_on_open_bugs": True, "block_on_open_tasks": True},
                ui_config={"list_display": "more", "list_priority": 90},
            ),
            _transition(
                "cancel",
                "取消",
                "in_processing",
                "canceled",
                target_type="keep_current",
                validator_config={"type": "requirement_terminal_gate", "block_on_open_bugs": True, "block_on_open_tasks": True},
                ui_config={"list_display": "more", "list_priority": 90},
            ),
            _transition("reactivate", "重新激活", "canceled", "pending_assignment", target_type="keep_current"),
        ],
    )


def _task_graph() -> WorkflowGraphSave:
    return WorkflowGraphSave(
        states=[
            _state("pending_assignment", "待分派", "start", "#6b7280", 80, 120),
            _state("in_processing", "处理中", "normal", "#2563eb", 280, 120),
            _state("pending_confirmation", "待确认", "normal", "#7c3aed", 480, 120),
            _state("completed", "已完成", "terminal", "#059669", 680, 120),
            _state("canceled", "已取消", "terminal", "#94a3b8", 480, 260),
        ],
        transitions=[
            _transition("claim", "认领", "pending_assignment", "in_processing", target_type="actor"),
            _transition("assign", "指派", "pending_assignment", "in_processing", target_type="explicit_owner"),
            _transition(
                "complete",
                "完成",
                "in_processing",
                "completed",
                target_type="keep_current",
                condition_config={"task_types": ["requirement_implementation", "standalone_operation"]},
                ui_config={"list_display": "primary", "list_priority": 10},
            ),
            _transition(
                "submit_confirmation",
                "提交确认",
                "in_processing",
                "pending_confirmation",
                target_type="project_role",
                target_roles="project_owner",
                fallback_type="project_role",
                fallback_roles="project_owner",
                condition_config={"task_types": ["bug_fix", "test_support"]},
                ui_config={"list_display": "primary", "list_priority": 10},
            ),
            _transition("approve_confirmation", "确认通过", "pending_confirmation", "completed", target_type="keep_current"),
            _transition("return_rework", "退回返工", "pending_confirmation", "in_processing", target_type="previous_handler"),
            _transition("cancel", "取消", "pending_assignment", "canceled", target_type="keep_current"),
            _transition("cancel", "取消", "in_processing", "canceled", target_type="keep_current"),
            _transition("cancel", "取消", "pending_confirmation", "canceled", target_type="keep_current"),
            _transition("reactivate", "重新激活", "canceled", "pending_assignment", target_type="keep_current"),
        ],
    )


def _bug_graph() -> WorkflowGraphSave:
    return WorkflowGraphSave(
        states=[
            _state("pending_handling", "待处理", "start", "#6b7280", 80, 100),
            _state("fixing", "修复中", "normal", "#2563eb", 280, 100),
            _state("pending_verification", "待验证", "normal", "#7c3aed", 480, 100),
            _state("verified", "已验证", "normal", "#0f766e", 680, 100),
            _state("closed", "已关闭", "terminal", "#059669", 880, 100),
        ],
        transitions=[
            _transition(
                "claim",
                "认领",
                "pending_handling",
                "pending_handling",
                target_type="actor",
                ui_config={"list_display": "primary", "list_priority": 5, "ownerless_only": True},
            ),
            _transition(
                "assign",
                "指派",
                "pending_handling",
                "pending_handling",
                allowed_roles="project_owner",
                target_type="explicit_owner",
                allow_manual_owner=True,
                ui_config={"list_display": "more", "list_priority": 10, "ownerless_only": True},
            ),
            _transition(
                "confirm_bug_type",
                "确认缺陷类型",
                "pending_handling",
                "fixing",
                target_type="keep_current",
                condition_config={
                    "routing_mode": "automatic",
                    "field": "bug_type",
                    "routes": {
                        "code_issue": "fixing",
                        "configuration_issue": "fixing",
                        "data_issue": "fixing",
                        "environment_issue": "pending_verification",
                        "requirement_issue": "pending_verification",
                        "design_as_intended": "pending_verification",
                        "duplicate_issue": "pending_verification",
                        "cannot_reproduce": "pending_verification",
                        "operation_issue": "pending_verification",
                    },
                },
                form_config={"fields": [{"field": "bug_type", "type": "select", "required": True}]},
                ui_config={"list_display": "primary", "list_priority": 10},
            ),
            _transition(
                "reclassify_bug_type",
                "重新判定缺陷类型",
                "fixing",
                "fixing",
                target_type="keep_current",
                condition_config={
                    "routing_mode": "automatic_with_override",
                    "field": "bug_type",
                    "routes": {
                        "code_issue": "fixing",
                        "configuration_issue": "fixing",
                        "data_issue": "fixing",
                        "environment_issue": "pending_verification",
                        "requirement_issue": "pending_verification",
                        "design_as_intended": "pending_verification",
                        "duplicate_issue": "pending_verification",
                        "cannot_reproduce": "pending_verification",
                        "operation_issue": "pending_verification",
                    },
                    "allow_override_roles": ["project_owner", "system_admin"],
                },
                form_config={"fields": [{"field": "bug_type", "type": "select", "required": True}]},
                ui_config={"list_display": "more", "list_priority": 40},
            ),
            _transition(
                "submit_verification",
                "提交验证",
                "fixing",
                "pending_verification",
                target_type="project_role",
                target_roles="tester,project_owner",
                fallback_type="project_role",
                fallback_roles="project_owner",
                ui_config={"list_display": "primary", "list_priority": 10},
            ),
            _transition("verification_passed", "验证通过", "pending_verification", "verified", ui_config={"list_display": "primary", "list_priority": 10}),
            _transition("verification_failed", "验证不通过", "pending_verification", "pending_handling", target_type="previous_handler", ui_config={"list_display": "primary", "list_priority": 20}),
            _transition("return_reopen", "退回打开", "verified", "pending_handling", target_type="previous_handler", ui_config={"list_display": "more", "list_priority": 20}),
            _transition(
                "close",
                "关闭",
                "verified",
                "closed",
                target_type="keep_current",
                validator_config={"type": "bug_close_gate", "direct_tasks_terminal_statuses": ["completed", "canceled"]},
                ui_config={"list_display": "primary", "list_priority": 10},
            ),
            _transition("activate", "激活", "closed", "pending_handling", target_type="previous_handler"),
        ],
    )


def _iteration_graph() -> WorkflowGraphSave:
    return WorkflowGraphSave(
        states=[
            _state("planning", "规划中", "start", "#6b7280", 80, 120),
            _state("active", "进行中", "normal", "#2563eb", 280, 120),
            _state("completed", "已完成", "terminal", "#059669", 480, 120),
            _state("canceled", "已取消", "terminal", "#94a3b8", 480, 260),
        ],
        transitions=[
            _transition("start", "开始", "planning", "active"),
            _transition("complete", "完成", "active", "completed", validator_config={"type": "iteration_terminal_gate"}),
            _transition("cancel", "取消", "active", "canceled", validator_config={"type": "iteration_terminal_gate"}),
        ],
    )


def _project_graph() -> WorkflowGraphSave:
    return WorkflowGraphSave(
        states=[
            _state("planning", "规划中", "start", "#6b7280", 80, 120),
            _state("active", "进行中", "normal", "#2563eb", 280, 120),
            _state("paused", "已暂停", "normal", "#7c3aed", 480, 120),
            _state("closed", "已关闭", "terminal", "#059669", 680, 120),
        ],
        transitions=[
            _transition("start", "开始", "planning", "active"),
            _transition("suspend", "暂停", "active", "paused"),
            _transition("resume", "恢复", "paused", "active"),
            _transition("close", "关闭", "active", "closed", validator_config={"type": "project_close_gate"}),
            _transition("close", "关闭", "paused", "closed", validator_config={"type": "project_close_gate"}),
        ],
    )


def _state(status_key: str, status_name: str, category: str, color: str, x: int, y: int) -> WorkflowStateBase:
    return WorkflowStateBase(status_key=status_key, status_name=status_name, category=category, color=color, x=x, y=y)


def _transition(
    action_key: str,
    action_name: str,
    from_status: str,
    to_status: str,
    *,
    allowed_roles: str = "",
    target_type: str = "keep_current",
    target_roles: str = "",
    fallback_type: str = "keep_current",
    fallback_roles: str = "",
    allow_manual_owner: bool = False,
    manual_owner_roles: str = "",
    condition_config: dict | None = None,
    validator_config: dict | None = None,
    form_config: dict | None = None,
    ui_config: dict | None = None,
) -> WorkflowTransitionBase:
    resolved_allowed_roles = allowed_roles
    resolved_allow_manual_owner = allow_manual_owner
    resolved_ui_config = dict(ui_config or {})
    if action_key in {"claim", "assign"} and from_status in {"pending_assignment", "pending_handling"}:
        resolved_ui_config.setdefault("ownerless_only", True)
        if action_key == "claim":
            resolved_ui_config.setdefault("list_display", "primary")
            resolved_ui_config.setdefault("list_priority", 10)
        if action_key == "assign":
            resolved_allowed_roles = resolved_allowed_roles or "project_owner"
            resolved_allow_manual_owner = True
            resolved_ui_config.setdefault("list_display", "more")
            resolved_ui_config.setdefault("list_priority", 20)
    return WorkflowTransitionBase(
        action_key=action_key,
        action_name=action_name,
        from_status=from_status,
        to_status=to_status,
        allowed_roles=resolved_allowed_roles,
        handler_rule={
            "target_type": target_type,
            "target_roles": target_roles,
            "fallback_type": fallback_type,
            "fallback_roles": fallback_roles,
            "allow_manual_owner": resolved_allow_manual_owner,
            "manual_owner_roles": manual_owner_roles,
        },
        condition_config=condition_config,
        validator_config=validator_config,
        form_config=form_config,
        ui_config=resolved_ui_config,
    )

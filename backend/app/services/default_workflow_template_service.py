from datetime import datetime

from sqlalchemy.orm import Session

from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.views.workflow_definition_view import (
    WorkflowTemplateGraph as WorkflowGraphSave,
    WorkflowTemplateState as WorkflowStateBase,
    WorkflowTemplateTransition as WorkflowTransitionBase,
)


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
            _reconcile_graph(db, definition, spec["graph"])
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
            if _reconcile_graph(db, definition, spec["graph"]):
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


def _reconcile_graph(db: Session, definition: WorkflowDefinition, graph: WorkflowGraphSave) -> bool:
    changed = False
    existing_states = {
        item.status_key: item
        for item in db.query(WorkflowState).filter(WorkflowState.definition_id == definition.id).all()
    }
    state_by_key: dict[str, WorkflowState] = {}
    for item in graph.states:
        state = existing_states.get(item.status_key)
        data = item.model_dump(exclude={"status_key"})
        if not state:
            state = WorkflowState(definition_id=definition.id, status_key=item.status_key, **data)
            db.add(state)
            db.flush()
            changed = True
        else:
            for field, value in data.items():
                if getattr(state, field) != value:
                    setattr(state, field, value)
                    changed = True
        state_by_key[item.status_key] = state

    for status_key, state in existing_states.items():
        if status_key not in state_by_key and state.enabled:
            state.enabled = False
            changed = True

    existing_transitions = {
        (item.action_key, item.from_status, item.to_status): item
        for item in db.query(WorkflowTransition).filter(WorkflowTransition.definition_id == definition.id).all()
    }
    kept_transition_ids: set[int] = set()
    for item in graph.transitions:
        key = (item.action_key, item.from_status, item.to_status)
        transition = existing_transitions.get(key)
        condition_config = _template_condition_config(item.condition_config, state_by_key)
        data = item.model_dump(exclude={"from_status", "to_status", "condition_config"})
        data.update(
            {
                "from_status": item.from_status,
                "to_status": item.to_status,
                "from_state_id": state_by_key[item.from_status].id,
                "to_state_id": state_by_key[item.to_status].id,
                "condition_config": condition_config,
            }
        )
        if not transition:
            transition = WorkflowTransition(definition_id=definition.id, **data)
            db.add(transition)
            db.flush()
            changed = True
        else:
            for field, value in data.items():
                if getattr(transition, field) != value:
                    setattr(transition, field, value)
                    changed = True
        kept_transition_ids.add(transition.id)

    omitted_transition_ids = set(item.id for item in existing_transitions.values()) - kept_transition_ids
    if omitted_transition_ids:
        db.query(WorkflowTransition).filter(WorkflowTransition.id.in_(omitted_transition_ids)).delete(
            synchronize_session=False
        )
        changed = True

    initial = next((item for item in graph.states if item.category == "start" and item.enabled), None)
    initial_state_id = state_by_key[initial.status_key].id if initial else None
    if definition.initial_state_id != initial_state_id:
        definition.initial_state_id = initial_state_id
        changed = True
    return changed


def _template_condition_config(config: dict | list | None, state_by_key: dict[str, WorkflowState]):
    if not config or not isinstance(config, dict):
        return config
    result = dict(config)
    if isinstance(result.get("routes"), dict):
        result["routes"] = {key: state_by_key[value].id for key, value in result["routes"].items()}
    owner_targets = result.pop("target_status_by_owner", None)
    if owner_targets is not None:
        result["target_state_id_by_owner"] = {
            key: state_by_key[value].id for key, value in owner_targets.items()
        }
    return result


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
            _transition(
                "claim",
                "认领",
                "pending_assignment",
                "in_processing",
                allowed_roles="project_member",
                target_type="actor",
                handler_scope="project_member",
            ),
            _transition("assign", "指派", "pending_assignment", "in_processing", target_type="explicit_owner"),
            _command_transition("edit", "编辑", "pending_assignment", allowed_roles="creator", command_type="edit"),
            _command_transition(
                "add_information",
                "补充信息",
                "pending_assignment",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _transition(
                "complete",
                "完成",
                "in_processing",
                "completed",
                target_type="keep_current",
                validator_config={"type": "requirement_terminal_gate", "block_on_open_bugs": True, "block_on_open_tasks": True},
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _ownership_transition("transfer", "转派", "in_processing"),
            _ownership_transition("change_handler", "变更处理人", "in_processing", management=True),
            _ownership_transition("transfer_confirmation", "转移确认", "pending_confirmation"),
            _ownership_transition(
                "change_confirmation_handler",
                "变更确认处理人",
                "pending_confirmation",
                management=True,
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "in_processing",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "pending_confirmation",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _transition(
                "cancel",
                "取消",
                "pending_assignment",
                "canceled",
                allowed_roles="creator,project_owner",
                target_type="keep_current",
                validator_config={"type": "requirement_terminal_gate", "block_on_open_bugs": True, "block_on_open_tasks": True},
                handler_scope="allowed_identity",
                ui_config={"list_display": "more", "list_priority": 90, "button_type": "danger"},
            ),
            _transition(
                "cancel",
                "取消",
                "in_processing",
                "canceled",
                allowed_roles="current_handler,project_owner",
                target_type="keep_current",
                validator_config={"type": "requirement_terminal_gate", "block_on_open_bugs": True, "block_on_open_tasks": True},
                handler_scope="allowed_identity",
                ui_config={"list_display": "more", "list_priority": 90, "button_type": "danger", "requires_owner": True},
            ),
            _transition(
                "cancel",
                "取消",
                "pending_confirmation",
                "canceled",
                allowed_roles="current_handler,project_owner",
                target_type="keep_current",
                validator_config={"type": "requirement_terminal_gate", "block_on_open_bugs": True, "block_on_open_tasks": True},
                handler_scope="allowed_identity",
                ui_config={"list_display": "more", "list_priority": 90, "button_type": "danger", "requires_owner": True},
            ),
            _reactivate_transition("canceled", allowed_roles="creator,project_owner"),
            _reactivate_transition("completed", allowed_roles="creator,project_owner"),
            _command_transition(
                "view_history",
                "查看历史",
                "canceled",
                allowed_roles="project_member,creator",
                command_type="view_history",
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "canceled",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _command_transition(
                "view_history",
                "查看历史",
                "completed",
                allowed_roles="project_member,creator",
                command_type="view_history",
            ),
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
            _transition(
                "claim",
                "认领",
                "pending_assignment",
                "in_processing",
                allowed_roles="project_member",
                target_type="actor",
                handler_scope="project_member",
            ),
            _transition("assign", "指派", "pending_assignment", "in_processing", target_type="explicit_owner"),
            _command_transition("edit", "编辑", "pending_assignment", allowed_roles="creator", command_type="edit"),
            _command_transition(
                "add_information",
                "补充信息",
                "pending_assignment",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _transition(
                "complete",
                "完成",
                "in_processing",
                "completed",
                target_type="keep_current",
                condition_config={"task_types": ["requirement_implementation", "standalone_operation"]},
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _transition(
                "submit_confirmation",
                "提交确认",
                "in_processing",
                "pending_confirmation",
                target_type="task_confirmation",
                fallback_type="project_role",
                fallback_roles="project_owner",
                condition_config={"task_types": ["bug_fix", "test_support"]},
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _ownership_transition("transfer", "转派", "in_processing"),
            _ownership_transition("change_handler", "变更处理人", "in_processing", management=True),
            _command_transition(
                "add_information",
                "补充信息",
                "in_processing",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _transition(
                "approve_confirmation",
                "确认通过",
                "pending_confirmation",
                "completed",
                target_type="keep_current",
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _transition(
                "return_rework",
                "退回返工",
                "pending_confirmation",
                "in_processing",
                target_type="previous_handler",
                handler_scope="current_handler",
                form_config={"fields": [{"field": "reason", "label": "退回原因", "type": "textarea", "required": True}]},
                ui_config={"list_display": "more", "list_priority": 20, "requires_owner": True},
            ),
            _ownership_transition("transfer_confirmation", "转移确认", "pending_confirmation"),
            _ownership_transition(
                "change_confirmation_handler",
                "变更确认处理人",
                "pending_confirmation",
                management=True,
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "pending_confirmation",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _transition(
                "cancel",
                "取消",
                "pending_assignment",
                "canceled",
                allowed_roles="creator,project_owner",
                target_type="keep_current",
                handler_scope="allowed_identity",
                ui_config={"button_type": "danger", "list_display": "more", "list_priority": 90},
            ),
            _transition(
                "cancel",
                "取消",
                "in_processing",
                "canceled",
                allowed_roles="current_handler,project_owner",
                target_type="keep_current",
                handler_scope="allowed_identity",
                ui_config={"button_type": "danger", "list_display": "more", "list_priority": 90, "requires_owner": True},
            ),
            _transition(
                "cancel",
                "取消",
                "pending_confirmation",
                "canceled",
                allowed_roles="project_owner",
                target_type="keep_current",
                handler_scope="allowed_identity",
                ui_config={"button_type": "danger", "list_display": "more", "list_priority": 90, "requires_owner": True},
            ),
            _reactivate_transition("canceled", allowed_roles="creator,project_owner"),
            _command_transition(
                "view_history",
                "查看历史",
                "canceled",
                allowed_roles="project_member,creator",
                command_type="view_history",
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "canceled",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
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
                allowed_roles="project_member",
                target_type="actor",
                handler_scope="project_member",
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
            _ownership_transition("transfer", "转派", "pending_handling"),
            _ownership_transition("change_handler", "变更处理人", "pending_handling", management=True),
            _transition(
                "confirm_bug_type",
                "确认缺陷类型",
                "pending_handling",
                "fixing",
                target_type="bug_verifier_if_pending_verification",
                condition_config={
                    "routing_mode": "automatic",
                    "field": "bug_type",
                    "route_dictionary": "bug_type",
                },
                form_config={"fields": [{"field": "bug_type", "label": "Bug 类型", "type": "select", "dictionary": "bug_type", "required": True}]},
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _bug_void_transition("pending_handling"),
            _command_transition(
                "add_information",
                "补充信息",
                "pending_handling",
                allowed_roles="reporter,tester",
                command_type="add_information",
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
                    "route_dictionary": "bug_type",
                    "allow_override_roles": ["project_owner", "system_admin"],
                },
                form_config={
                    "fields": [
                        {"field": "bug_type", "label": "Bug 类型", "type": "select", "dictionary": "bug_type", "required": True},
                        {"field": "reason", "label": "重分类原因", "type": "textarea", "required": True},
                    ]
                },
                handler_scope="current_handler",
                ui_config={"list_display": "more", "list_priority": 40, "requires_owner": True},
            ),
            _transition(
                "submit_verification",
                "提交验证",
                "fixing",
                "pending_verification",
                target_type="bug_verifier",
                fallback_type="project_role",
                fallback_roles="project_owner",
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _ownership_transition("transfer", "转派", "fixing"),
            _ownership_transition("change_handler", "变更处理人", "fixing", management=True),
            _bug_void_transition("fixing"),
            _command_transition(
                "add_information",
                "补充信息",
                "fixing",
                allowed_roles="reporter,tester",
                command_type="add_information",
            ),
            _transition(
                "verification_passed",
                "验证通过",
                "pending_verification",
                "verified",
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _transition(
                "verification_failed",
                "验证不通过",
                "pending_verification",
                "pending_handling",
                target_type="previous_handler",
                handler_scope="current_handler",
                form_config={"fields": [{"field": "reason", "label": "验证不通过原因", "type": "textarea", "required": True}]},
                ui_config={"list_display": "primary", "list_priority": 20, "requires_owner": True},
            ),
            _ownership_transition("transfer_verification", "转移验证", "pending_verification"),
            _ownership_transition("assign_verifier", "指派验证人", "pending_verification", management=True),
            _bug_void_transition("pending_verification"),
            _command_transition(
                "add_information",
                "补充信息",
                "pending_verification",
                allowed_roles="reporter,tester",
                command_type="add_information",
            ),
            _transition(
                "return_reopen",
                "退回打开",
                "verified",
                "pending_handling",
                allowed_roles="reporter,tester,project_owner",
                target_type="previous_handler",
                handler_scope="allowed_identity",
                form_config={"fields": [{"field": "reason", "label": "退回原因", "type": "textarea", "required": True}]},
                ui_config={"list_display": "more", "list_priority": 20},
            ),
            _transition(
                "close",
                "关闭",
                "verified",
                "closed",
                allowed_roles="current_handler,project_owner",
                target_type="keep_current",
                validator_config={"type": "bug_close_gate", "direct_tasks_terminal_statuses": ["completed", "canceled"]},
                handler_scope="allowed_identity",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "verified",
                allowed_roles="project_member,reporter,tester",
                command_type="add_information",
            ),
            _command_transition(
                "view_history",
                "查看历史",
                "verified",
                allowed_roles="project_member,reporter,tester",
                command_type="view_history",
            ),
            _transition(
                "activate",
                "激活",
                "closed",
                "pending_handling",
                allowed_roles="reporter,tester,project_owner",
                target_type="previous_handler",
                handler_scope="allowed_identity",
                form_config={"fields": [{"field": "reason", "label": "激活原因", "type": "textarea", "required": True}]},
                ui_config={"list_display": "primary", "list_priority": 10},
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "closed",
                allowed_roles="project_member,reporter,tester",
                command_type="add_information",
            ),
            _command_transition(
                "view_history",
                "查看历史",
                "closed",
                allowed_roles="project_member,reporter,tester",
                command_type="view_history",
            ),
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
    handler_scope: str | None = None,
) -> WorkflowTransitionBase:
    resolved_allowed_roles = allowed_roles
    resolved_allow_manual_owner = allow_manual_owner
    resolved_ui_config = dict(ui_config or {})
    resolved_ui_config.setdefault("action_category", "process")
    if handler_scope:
        resolved_ui_config["handler_scope"] = handler_scope
    if action_key in {"claim", "assign"} and from_status in {"pending_assignment", "pending_handling"}:
        resolved_ui_config.setdefault("ownerless_only", True)
        if action_key == "claim":
            resolved_ui_config["handler_scope"] = handler_scope or "project_member"
            resolved_ui_config["action_category"] = "ownership"
            resolved_ui_config.setdefault("list_display", "primary")
            resolved_ui_config.setdefault("list_priority", 10)
        if action_key == "assign":
            resolved_allowed_roles = resolved_allowed_roles or "project_owner"
            resolved_allow_manual_owner = True
            resolved_ui_config["handler_scope"] = handler_scope or "allowed_identity"
            resolved_ui_config["action_category"] = "management"
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


def _ownership_transition(
    action_key: str,
    action_name: str,
    current_status: str,
    *,
    management: bool = False,
) -> WorkflowTransitionBase:
    return _transition(
        action_key,
        action_name,
        current_status,
        current_status,
        allowed_roles="project_owner" if management else "",
        target_type="explicit_owner",
        allow_manual_owner=True,
        form_config={
            "title": action_name,
            "fields": [
                {"field": "reason", "label": "原因", "type": "textarea", "required": False},
            ],
        },
        ui_config={
            "button_type": "warning" if management else "primary",
            "list_display": "more",
            "list_priority": 70 if management else 60,
            "action_category": "management" if management else "ownership",
            "handler_scope": "allowed_identity" if management else "current_handler",
            "requires_owner": True,
        },
    )


def _command_transition(
    action_key: str,
    action_name: str,
    current_status: str,
    *,
    allowed_roles: str,
    command_type: str,
) -> WorkflowTransitionBase:
    fields = []
    if command_type == "add_information":
        fields = [{"field": "content", "label": "补充内容", "type": "textarea", "required": True}]
    return _transition(
        action_key,
        action_name,
        current_status,
        current_status,
        allowed_roles=allowed_roles,
        handler_scope="allowed_identity",
        form_config={"fields": fields} if fields else None,
        ui_config={
            "command_type": command_type,
            "action_category": "information" if command_type == "add_information" else "navigation",
            "button_type": "primary",
            "list_display": "more",
            "list_priority": 80,
        },
    )


def _reactivate_transition(from_status: str, *, allowed_roles: str) -> WorkflowTransitionBase:
    return _transition(
        "reactivate",
        "重新激活",
        from_status,
        "pending_assignment",
        allowed_roles=allowed_roles,
        target_type="keep_current",
        allow_manual_owner=True,
        condition_config={
            "target_status_by_owner": {
                "with_owner": "in_processing",
                "without_owner": "pending_assignment",
            }
        },
        handler_scope="allowed_identity",
        form_config={"fields": [{"field": "reason", "label": "重新激活原因", "type": "textarea", "required": True}]},
        ui_config={"list_display": "primary", "list_priority": 10},
    )


def _bug_void_transition(from_status: str) -> WorkflowTransitionBase:
    return _transition(
        "void_close",
        "作废/关闭",
        from_status,
        "closed",
        allowed_roles="project_owner",
        target_type="keep_current",
        validator_config={"type": "bug_close_gate", "direct_tasks_terminal_statuses": ["completed", "canceled"]},
        handler_scope="allowed_identity",
        form_config={"fields": [{"field": "reason", "label": "作废/关闭原因", "type": "textarea", "required": True}]},
        ui_config={
            "button_type": "danger",
            "list_display": "more",
            "list_priority": 90,
            "action_category": "management",
        },
    )

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.status_operation import StatusOperationLog
from app.models.workflow_definition import WorkflowState


def _create_config(client: TestClient) -> int:
    response = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Designer Config {uuid4().hex[:8]}",
            "requirement_owner_roles": "product_owner",
            "task_owner_roles": "developer",
            "test_case_tester_roles": "tester",
            "test_run_owner_roles": "tester",
            "bug_owner_roles": "developer",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_and_list_workflow_definition(client: TestClient):
    config_id = _create_config(client)

    created = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": "Bug visual workflow",
            "object_type": "bug",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
            "enabled": True,
        },
    )

    assert created.status_code == 201
    data = created.json()
    assert data["name"] == "Bug visual workflow"
    assert data["object_type"] == "bug"
    assert data["scope_id"] == config_id

    listed = client.get(f"/api/v1/workflow-definitions?object_type=bug&scope_id={config_id}")
    assert listed.status_code == 200
    assert data["id"] in {item["id"] for item in listed.json()}


def test_graph_save_generates_private_identity_and_protects_persisted_transition(client: TestClient):
    config_id = _create_config(client)
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": f"Protected transition workflow {uuid4().hex[:8]}",
            "object_type": "requirement",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
        },
    ).json()
    payload = {
        "initial_state_id": -1,
        "states": [
            {"id": -1, "status_name": "待处理", "category": "start"},
            {"id": -2, "status_name": "处理中", "category": "normal"},
        ],
        "transitions": [
            {
                "action_name": "开始处理",
                "from_state_id": -1,
                "to_state_id": -2,
                "ui_config": {"list_display": "primary"},
                "sort_order": 10,
            }
        ],
    }

    saved = client.put(f"/api/v1/workflow-definitions/{definition['id']}/graph", json=payload)

    assert saved.status_code == 200, saved.text
    assert "action_key" not in saved.json()["transitions"][0]
    protected_payload = {
        "initial_state_id": saved.json()["definition"]["initial_state_id"],
        "states": saved.json()["states"],
        "transitions": [],
    }
    rejected = client.put(f"/api/v1/workflow-definitions/{definition['id']}/graph", json=protected_payload)
    assert rejected.status_code == 422
    assert "cannot be deleted" in rejected.json()["detail"].lower()


def test_graph_rejects_duplicate_enabled_names_and_invalid_button_group(client: TestClient):
    config_id = _create_config(client)
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": f"Validated transition workflow {uuid4().hex[:8]}",
            "object_type": "requirement",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
        },
    ).json()
    base = {
        "initial_state_id": -1,
        "states": [
            {"id": -1, "status_name": "待处理", "category": "start"},
            {"id": -2, "status_name": "处理中", "category": "normal"},
        ],
    }
    duplicate = client.put(
        f"/api/v1/workflow-definitions/{definition['id']}/graph",
        json={
            **base,
            "transitions": [
                {"action_name": "处理", "from_state_id": -1, "to_state_id": -2},
                {"action_name": "处理", "from_state_id": -1, "to_state_id": -1},
            ],
        },
    )
    invalid_group = client.put(
        f"/api/v1/workflow-definitions/{definition['id']}/graph",
        json={
            **base,
            "transitions": [
                {
                    "action_name": "处理",
                    "from_state_id": -1,
                    "to_state_id": -2,
                    "ui_config": {"list_display": "hidden"},
                }
            ],
        },
    )

    assert duplicate.status_code == 422
    assert invalid_group.status_code == 422


def test_graph_save_remaps_temporary_ids_and_preserves_ids_when_state_is_renamed(client: TestClient):
    config_id = _create_config(client)
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": f"ID graph workflow {uuid4().hex[:8]}",
            "object_type": "requirement",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
        },
    ).json()
    first_payload = {
        "initial_state_id": -1,
        "states": [
            {"id": -1, "status_name": "待处理", "category": "start", "x": 100, "y": 80},
            {"id": -2, "status_name": "处理中", "category": "normal", "x": 320, "y": 80},
        ],
        "transitions": [
            {
                "action_name": "开始处理",
                "from_state_id": -1,
                "to_state_id": -2,
            }
        ],
    }

    first = client.put(f"/api/v1/workflow-definitions/{definition['id']}/graph", json=first_payload)

    assert first.status_code == 200
    first_graph = first.json()
    first_states = {item["status_name"]: item for item in first_graph["states"]}
    start_id = first_states["待处理"]["id"]
    active_id = first_states["处理中"]["id"]
    transition_id = first_graph["transitions"][0]["id"]
    assert start_id > 0 and active_id > 0
    assert first_graph["definition"]["initial_state_id"] == start_id
    assert first_graph["transitions"][0]["from_state_id"] == start_id
    assert first_graph["transitions"][0]["to_state_id"] == active_id
    assert "status_key" not in first_states["待处理"]
    assert "from_status" not in first_graph["transitions"][0]
    assert "to_status" not in first_graph["transitions"][0]

    second_payload = {
        "initial_state_id": start_id,
        "states": [
            {**first_states["待处理"], "status_name": "待受理"},
            first_states["处理中"],
        ],
        "transitions": [
            {key: value for key, value in item.items() if key != "definition_id"}
            for item in first_graph["transitions"]
        ],
    }
    second = client.put(f"/api/v1/workflow-definitions/{definition['id']}/graph", json=second_payload)

    assert second.status_code == 200
    second_graph = second.json()
    assert {item["id"] for item in second_graph["states"]} == {start_id, active_id}
    assert next(item for item in second_graph["states"] if item["id"] == start_id)["status_name"] == "待受理"
    assert second_graph["transitions"][0]["id"] == transition_id


def test_graph_save_deletes_unreferenced_states_and_disables_referenced_states(client: TestClient):
    config_id = _create_config(client)
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": f"Referenced state workflow {uuid4().hex[:8]}",
            "object_type": "requirement",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
        },
    ).json()
    created = client.put(
        f"/api/v1/workflow-definitions/{definition['id']}/graph",
        json={
            "initial_state_id": -1,
            "states": [
                {"id": -1, "status_name": "开始", "category": "start"},
                {"id": -2, "status_name": "有历史引用", "category": "normal"},
                {"id": -3, "status_name": "无引用", "category": "normal"},
            ],
            "transitions": [],
        },
    ).json()
    states = {item["status_name"]: item for item in created["states"]}
    with SessionLocal() as db:
        db.add(
            StatusOperationLog(
                object_type="requirement",
                object_id=999999,
                action="migration-test",
                workflow_definition_id=definition["id"],
                from_state_id=states["有历史引用"]["id"],
                to_state_id=states["有历史引用"]["id"],
                from_state_name="有历史引用",
                to_state_name="有历史引用",
                from_status="legacy",
                to_status="legacy",
                effective_time=datetime.now(),
            )
        )
        db.commit()

    saved = client.put(
        f"/api/v1/workflow-definitions/{definition['id']}/graph",
        json={
            "initial_state_id": states["开始"]["id"],
            "states": [states["开始"]],
            "transitions": [],
        },
    )

    assert saved.status_code == 200, saved.text
    by_name = {item["status_name"]: item for item in saved.json()["states"]}
    assert "无引用" not in by_name
    assert by_name["有历史引用"]["enabled"] is False


def test_graph_save_rejects_cross_definition_and_disabled_initial_state_ids(client: TestClient):
    config_id = _create_config(client)
    definitions = [
        client.post(
            "/api/v1/workflow-definitions",
            json={
                "name": f"Cross definition {index}-{uuid4().hex[:8]}",
                "object_type": "task",
                "scope_type": "assignee_rule_config",
                "scope_id": config_id,
            },
        ).json()
        for index in range(2)
    ]
    first = client.put(
        f"/api/v1/workflow-definitions/{definitions[0]['id']}/graph",
        json={
            "initial_state_id": -1,
            "states": [{"id": -1, "status_name": "第一张图", "category": "start"}],
            "transitions": [],
        },
    ).json()
    foreign_state = first["states"][0]

    cross_definition = client.put(
        f"/api/v1/workflow-definitions/{definitions[1]['id']}/graph",
        json={
            "initial_state_id": foreign_state["id"],
            "states": [foreign_state],
            "transitions": [],
        },
    )
    disabled_initial = client.put(
        f"/api/v1/workflow-definitions/{definitions[1]['id']}/graph",
        json={
            "initial_state_id": -1,
            "states": [{"id": -1, "status_name": "停用开始", "category": "start", "enabled": False}],
            "transitions": [],
        },
    )

    assert cross_definition.status_code == 422
    assert disabled_initial.status_code == 422


def test_apply_template_creates_graph_nodes_and_transitions(client: TestClient):
    config_id = _create_config(client)
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": "Bug template workflow",
            "object_type": "bug",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
        },
    ).json()

    applied = client.post(f"/api/v1/workflow-definitions/{definition['id']}/apply-template")

    assert applied.status_code == 200
    graph = applied.json()
    assert {node["status_name"] for node in graph["states"]} == {
        "待处理",
        "修复中",
        "待验证",
        "已验证",
        "已关闭",
    }
    names_by_id = {node["id"]: node["status_name"] for node in graph["states"]}
    assert any(edge["action_name"] == "提交验证" and names_by_id[edge["to_state_id"]] == "待验证" for edge in graph["transitions"])
    assert any(edge["action_name"] == "验证通过" and names_by_id[edge["to_state_id"]] == "已验证" for edge in graph["transitions"])
    assert any(edge["action_name"] == "关闭" and names_by_id[edge["to_state_id"]] == "已关闭" for edge in graph["transitions"])


def test_apply_template_reuses_state_ids_on_repeated_application(client: TestClient):
    config_id = _create_config(client)
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": f"Repeat template workflow {uuid4().hex[:8]}",
            "object_type": "requirement",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
        },
    ).json()

    first = client.post(f"/api/v1/workflow-definitions/{definition['id']}/apply-template")
    second = client.post(f"/api/v1/workflow-definitions/{definition['id']}/apply-template")

    assert first.status_code == 200
    assert second.status_code == 200
    first_ids = {
        (item["status_name"], item["category"]): item["id"]
        for item in first.json()["states"]
        if item["enabled"]
    }
    second_ids = {
        (item["status_name"], item["category"]): item["id"]
        for item in second.json()["states"]
        if item["enabled"]
    }
    assert second_ids == first_ids
    assert len(second_ids) == 5
    assert len(second.json()["states"]) == 5


def test_apply_template_reuses_and_enables_unique_disabled_state(client: TestClient):
    config_id = _create_config(client)
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": f"Disabled template workflow {uuid4().hex[:8]}",
            "object_type": "bug",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
        },
    ).json()
    first = client.post(f"/api/v1/workflow-definitions/{definition['id']}/apply-template").json()
    disabled = next(item for item in first["states"] if item["status_name"] == "修复中")
    with SessionLocal() as db:
        state = db.get(WorkflowState, disabled["id"])
        state.enabled = False
        db.commit()

    applied = client.post(f"/api/v1/workflow-definitions/{definition['id']}/apply-template")

    assert applied.status_code == 200
    reused = next(item for item in applied.json()["states"] if item["status_name"] == "修复中")
    assert reused["id"] == disabled["id"]
    assert reused["enabled"] is True


def test_apply_template_rejects_ambiguous_semantic_state_matches(client: TestClient):
    config_id = _create_config(client)
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": f"Ambiguous template workflow {uuid4().hex[:8]}",
            "object_type": "task",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
        },
    ).json()
    first = client.post(f"/api/v1/workflow-definitions/{definition['id']}/apply-template").json()
    existing = first["states"][0]
    with SessionLocal() as db:
        db.add(
            WorkflowState(
                definition_id=definition["id"],
                status_name=existing["status_name"],
                category=existing["category"],
                color=existing["color"],
                enabled=True,
            )
        )
        db.commit()

    applied = client.post(f"/api/v1/workflow-definitions/{definition['id']}/apply-template")

    assert applied.status_code == 422
    assert existing["status_name"] in applied.json()["detail"]


def test_save_graph_preserves_layout_and_validates_duplicates(client: TestClient):
    config_id = _create_config(client)
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": "Requirement graph workflow",
            "object_type": "requirement",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
        },
    ).json()
    payload = {
        "initial_state_id": -1,
        "states": [
            {"id": -1, "status_name": "Draft", "category": "start", "color": "#475569", "x": 120, "y": 80},
            {"id": -2, "status_name": "Active", "category": "normal", "color": "#2563eb", "x": 320, "y": 80},
        ],
        "transitions": [
            {
                "action_name": "Activate",
                "from_state_id": -1,
                "to_state_id": -2,
                "handler_rule": {"target_type": "project_role", "target_roles": "project_member", "fallback_type": "keep_current"},
            }
        ],
    }

    saved = client.put(f"/api/v1/workflow-definitions/{definition['id']}/graph", json=payload)

    assert saved.status_code == 200, saved.text
    states = {node["status_name"]: node for node in saved.json()["states"]}
    assert states["Active"]["x"] == 320
    assert states["Active"]["y"] == 80
    loaded = client.get(f"/api/v1/workflow-definitions/{definition['id']}")
    assert loaded.status_code == 200
    loaded_states = {node["status_name"]: node for node in loaded.json()["states"]}
    assert loaded_states["Draft"]["x"] == 120
    assert loaded_states["Draft"]["y"] == 80
    assert loaded_states["Active"]["x"] == 320
    assert loaded_states["Active"]["y"] == 80

    duplicate = dict(payload)
    duplicate["states"] = payload["states"] + [
        {"id": -2, "status_name": "Duplicate", "category": "normal", "x": 400, "y": 80}
    ]
    failed = client.put(f"/api/v1/workflow-definitions/{definition['id']}/graph", json=duplicate)
    assert failed.status_code == 422


def test_transition_handler_rule_is_persisted_only_on_transition(client: TestClient):
    config_id = _create_config(client)
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": "Task graph workflow",
            "object_type": "task",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
        },
    ).json()

    saved = client.put(
        f"/api/v1/workflow-definitions/{definition['id']}/graph",
        json={
            "initial_state_id": -1,
            "states": [
                {"id": -1, "status_name": "Todo", "category": "start", "x": 100, "y": 100},
                {"id": -2, "status_name": "Doing", "category": "normal", "x": 280, "y": 100},
            ],
            "transitions": [
                {
                    "action_name": "Activate",
                    "from_state_id": -1,
                    "to_state_id": -2,
                    "allowed_roles": "project_member",
                    "handler_rule": {
                        "target_type": "project_role",
                        "target_roles": "project_member",
                        "fallback_type": "keep_current",
                    },
                }
            ],
        },
    )

    assert saved.status_code == 200, saved.text
    state_ids = {item["status_name"]: item["id"] for item in saved.json()["states"]}
    transition = saved.json()["transitions"][0]
    assert transition["from_state_id"] == state_ids["Todo"]
    assert transition["to_state_id"] == state_ids["Doing"]
    assert transition["handler_rule"]["target_type"] == "project_role"
    assert transition["handler_rule"]["target_roles"] == "project_member"
    assert client.get(f"/api/v1/handler-transition-rules?config_id={config_id}").status_code == 404


def test_save_graph_preserves_transition_ui_and_form_config(client: TestClient):
    config_id = _create_config(client)
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": "Bug action config workflow",
            "object_type": "bug",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
        },
    ).json()

    saved = client.put(
        f"/api/v1/workflow-definitions/{definition['id']}/graph",
        json={
            "initial_state_id": -1,
            "states": [
                {"id": -1, "status_name": "Fixing", "category": "start", "x": 100, "y": 100},
                {"id": -2, "status_name": "Verifying", "category": "normal", "x": 300, "y": 100},
            ],
            "transitions": [
                {
                    "action_name": "确认解决",
                    "from_state_id": -1,
                    "to_state_id": -2,
                    "ui_config": {
                        "button_type": "success",
                        "list_display": "primary",
                    },
                    "form_config": {
                        "title": "解决 Bug",
                        "submit_text": "确认解决",
                        "fields": [
                            {
                                "field": "resolution",
                                "label": "解决方案",
                                "type": "select",
                                "required": True,
                                "options": [
                                    {"label": "Fixed", "value": "fixed"},
                                    {"label": "Rejected", "value": "rejected"},
                                ],
                            }
                        ],
                    },
                    "handler_rule": {
                        "target_type": "project_role",
                        "target_roles": "tester",
                        "fallback_type": "keep_current",
                    },
                }
            ],
        },
    )

    assert saved.status_code == 200, saved.text
    transition = saved.json()["transitions"][0]
    assert transition["ui_config"]["button_type"] == "success"
    assert transition["ui_config"]["list_display"] == "primary"
    assert transition["form_config"]["title"] == "解决 Bug"
    loaded = client.get(f"/api/v1/workflow-definitions/{definition['id']}")
    assert loaded.json()["transitions"][0]["form_config"]["fields"][0]["field"] == "resolution"


def _advanced_definition(client: TestClient) -> dict:
    config_id = _create_config(client)
    return client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": f"Advanced workflow {uuid4().hex[:8]}",
            "object_type": "bug",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
        },
    ).json()


def _advanced_graph(transition_overrides: dict | None = None) -> dict:
    transition = {
        "action_name": "Classify",
        "from_state_id": -1,
        "to_state_id": -2,
        "allowed_roles": "current_handler,system_admin",
        "handler_rule": {
            "target_type": "project_role",
            "target_roles": "project_member",
            "fallback_type": "project_owner",
        },
        "condition_config": {
            "field": "classification",
            "routes": {"real": -2, "invalid": -3},
            "routing_mode": "automatic_with_override",
            "allow_override_roles": ["system_admin"],
        },
        "form_config": {
            "title": "Classify Bug",
            "submit_text": "Confirm",
            "fields": [
                {
                    "field": "classification",
                    "label": "Classification",
                    "type": "select",
                    "required": True,
                    "options": [
                        {"label": "Real", "value": "real"},
                        {"label": "Invalid", "value": "invalid"},
                    ],
                }
            ],
        },
        "validator_config": {"type": "bug_close_gate"},
        "ui_config": {
            "button_type": "warning",
            "list_display": "primary",
            "action_category": "management",
        },
        "trigger_config": {
            "type": "notification",
            "receiver": "actor",
            "title": "Workflow started",
        },
        "post_action_config": {
            "type": "notification",
            "receiver": "next_handler",
            "title": "Work item assigned",
        },
    }
    transition.update(transition_overrides or {})
    return {
        "initial_state_id": -1,
        "states": [
            {"id": -1, "status_name": "Pending", "category": "start"},
            {"id": -2, "status_name": "Fixing", "category": "normal"},
            {"id": -3, "status_name": "Closed", "category": "terminal"},
        ],
        "transitions": [transition],
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"condition_config": {"field": "classification", "routes": {"real": -99}}},
        {"condition_config": {"field": "classification", "routes": {}}},
        {"form_config": {"fields": [{"field": "classification", "label": "Type", "type": "select"}]}},
        {"validator_config": {"type": "arbitrary_script"}},
        {"trigger_config": {"type": "webhook_script"}},
        {"post_action_config": {"type": "shell_command"}},
        {"allowed_roles": "unknown_workflow_role"},
        {"handler_rule": {"target_type": "unknown_resolver", "fallback_type": "keep_current"}},
    ],
)
def test_save_graph_rejects_unsupported_runtime_configuration(client: TestClient, overrides: dict):
    definition = _advanced_definition(client)

    response = client.put(
        f"/api/v1/workflow-definitions/{definition['id']}/graph",
        json=_advanced_graph(overrides),
    )

    assert response.status_code == 422


def test_save_graph_round_trips_controlled_runtime_configuration(client: TestClient):
    definition = _advanced_definition(client)
    payload = _advanced_graph()

    saved = client.put(f"/api/v1/workflow-definitions/{definition['id']}/graph", json=payload)
    loaded = client.get(f"/api/v1/workflow-definitions/{definition['id']}")

    assert saved.status_code == 200, saved.text
    assert loaded.status_code == 200
    transition = loaded.json()["transitions"][0]
    for field in [
        "form_config",
        "validator_config",
        "ui_config",
        "trigger_config",
        "post_action_config",
        "handler_rule",
    ]:
        assert transition[field] == payload["transitions"][0][field]
    state_ids = {item["status_name"]: item["id"] for item in loaded.json()["states"]}
    assert transition["condition_config"] == {
        **payload["transitions"][0]["condition_config"],
        "routes": {"real": state_ids["Fixing"], "invalid": state_ids["Closed"]},
    }
def test_default_template_definitions_exist_for_core_objects(client: TestClient):
    listed = client.get("/api/v1/workflow-definitions?scope_type=system")

    assert listed.status_code == 200
    by_object_type = {item["object_type"]: item for item in listed.json()}
    assert {"requirement", "task", "bug", "iteration", "project"} <= set(by_object_type)
    assert by_object_type["bug"]["is_default_template"] is True
    assert by_object_type["task"]["is_default_template"] is True
    assert by_object_type["requirement"]["name"] == "默认需求工作流模板"
    assert by_object_type["task"]["name"] == "默认任务工作流模板"
    assert by_object_type["bug"]["name"] == "默认缺陷工作流模板"
    assert by_object_type["iteration"]["name"] == "默认迭代工作流模板"
    assert by_object_type["project"]["name"] == "默认项目工作流模板"


def test_bug_default_template_matches_prd_baseline(client: TestClient):
    listed = client.get("/api/v1/workflow-definitions?object_type=bug&scope_type=system")
    assert listed.status_code == 200
    definition = next(item for item in listed.json() if item["is_default_template"] is True)

    graph = client.get(f"/api/v1/workflow-definitions/{definition['id']}")

    assert graph.status_code == 200
    states = {node["status_name"] for node in graph.json()["states"]}
    assert states == {"待处理", "修复中", "待验证", "已验证", "已关闭"}
    transition_names = {item["action_name"] for item in graph.json()["transitions"]}
    assert {"确认缺陷类型", "提交验证", "验证通过", "验证不通过", "关闭", "激活", "重新判定缺陷类型"} <= transition_names
    assert all("status_key" not in node for node in graph.json()["states"])
    assert all("action_key" not in item for item in graph.json()["transitions"])
    assert graph.json()["definition"]["template_key"] == "bug.default"


def test_requirement_and_project_default_templates_expose_default_metadata(client: TestClient):
    requirement_list = client.get("/api/v1/workflow-definitions?object_type=requirement&scope_type=system")
    project_list = client.get("/api/v1/workflow-definitions?object_type=project&scope_type=system")

    assert requirement_list.status_code == 200
    assert project_list.status_code == 200
    requirement_definition = next(item for item in requirement_list.json() if item["is_default_template"] is True)
    project_definition = next(item for item in project_list.json() if item["is_default_template"] is True)
    assert requirement_definition["template_key"] == "requirement.default"
    assert project_definition["template_key"] == "project.default"
    assert requirement_definition["name"] == "默认需求工作流模板"
    assert project_definition["name"] == "默认项目工作流模板"

    requirement_graph = client.get(f"/api/v1/workflow-definitions/{requirement_definition['id']}")
    assert requirement_graph.status_code == 200
    requirement_state_names = {node["status_name"] for node in requirement_graph.json()["states"]}
    assert requirement_state_names == {"待分派", "处理中", "待确认", "已完成", "已取消"}
    requirement_action_names = {item["action_name"] for item in requirement_graph.json()["transitions"]}
    assert {"认领", "指派", "完成", "取消", "重新激活"} <= requirement_action_names

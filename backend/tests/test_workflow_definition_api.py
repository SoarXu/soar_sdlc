from uuid import uuid4

from fastapi.testclient import TestClient


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
    assert [item["id"] for item in listed.json()] == [data["id"]]


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
    assert {node["status_key"] for node in graph["states"]} == {
        "pending_handling",
        "fixing",
        "pending_verification",
        "verified",
        "closed",
    }
    assert any(edge["action_key"] == "submit_verification" and edge["to_status"] == "pending_verification" for edge in graph["transitions"])
    assert any(edge["action_key"] == "verification_passed" and edge["to_status"] == "verified" for edge in graph["transitions"])
    assert any(edge["action_key"] == "close" and edge["to_status"] == "closed" for edge in graph["transitions"])


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
        "states": [
            {"status_key": "draft", "status_name": "Draft", "category": "start", "color": "#475569", "x": 120, "y": 80},
            {"status_key": "active", "status_name": "Active", "category": "normal", "color": "#2563eb", "x": 320, "y": 80},
        ],
        "transitions": [
            {
                "action_key": "activate",
                "action_name": "Activate",
                "from_status": "draft",
                "to_status": "active",
                "handler_rule": {"target_type": "project_role", "target_roles": "developer", "fallback_type": "keep_current"},
            }
        ],
    }

    saved = client.put(f"/api/v1/workflow-definitions/{definition['id']}/graph", json=payload)

    assert saved.status_code == 200
    states = {node["status_key"]: node for node in saved.json()["states"]}
    assert states["active"]["x"] == 320
    assert states["active"]["y"] == 80
    loaded = client.get(f"/api/v1/workflow-definitions/{definition['id']}")
    assert loaded.status_code == 200
    loaded_states = {node["status_key"]: node for node in loaded.json()["states"]}
    assert loaded_states["draft"]["x"] == 120
    assert loaded_states["draft"]["y"] == 80
    assert loaded_states["active"]["x"] == 320
    assert loaded_states["active"]["y"] == 80

    duplicate = dict(payload)
    duplicate["states"] = payload["states"] + [
        {"status_key": "active", "status_name": "Duplicate", "category": "normal", "x": 400, "y": 80}
    ]
    failed = client.put(f"/api/v1/workflow-definitions/{definition['id']}/graph", json=duplicate)
    assert failed.status_code == 422


def test_transition_handler_rule_syncs_to_handler_transition_rules(client: TestClient):
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
            "states": [
                {"status_key": "todo", "status_name": "Todo", "category": "start", "x": 100, "y": 100},
                {"status_key": "doing", "status_name": "Doing", "category": "normal", "x": 280, "y": 100},
            ],
            "transitions": [
                {
                    "action_key": "activate",
                    "action_name": "Activate",
                    "from_status": "todo",
                    "to_status": "doing",
                    "allowed_roles": "developer",
                    "handler_rule": {
                        "target_type": "project_role",
                        "target_roles": "developer",
                        "fallback_type": "keep_current",
                    },
                }
            ],
        },
    )

    assert saved.status_code == 200
    rules = client.get(f"/api/v1/handler-transition-rules?config_id={config_id}").json()
    rule = next(item for item in rules if item["object_type"] == "task" and item["action"] == "activate")
    assert rule["rule_type"] == "advanced"
    assert rule["from_status"] == "todo"
    assert rule["to_status"] == "doing"
    assert rule["target_roles"] == "developer"


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
            "states": [
                {"status_key": "fixing", "status_name": "Fixing", "category": "normal", "x": 100, "y": 100},
                {"status_key": "verifying", "status_name": "Verifying", "category": "normal", "x": 300, "y": 100},
            ],
            "transitions": [
                {
                    "action_key": "resolve",
                    "action_name": "确认解决",
                    "from_status": "fixing",
                    "to_status": "verifying",
                    "ui_config": {
                        "button_type": "success",
                        "list_display": "primary",
                        "list_priority": 10,
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
                                "options_source": "bug_resolutions",
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

    assert saved.status_code == 200
    transition = saved.json()["transitions"][0]
    assert transition["ui_config"]["button_type"] == "success"
    assert transition["ui_config"]["list_display"] == "primary"
    assert transition["form_config"]["title"] == "解决 Bug"
    loaded = client.get(f"/api/v1/workflow-definitions/{definition['id']}")
    assert loaded.json()["transitions"][0]["form_config"]["fields"][0]["field"] == "resolution"
def test_default_template_definitions_exist_for_core_objects(client: TestClient):
    listed = client.get("/api/v1/workflow-definitions?scope_type=system")

    assert listed.status_code == 200
    by_object_type = {item["object_type"]: item for item in listed.json()}
    assert {"requirement", "task", "bug", "iteration", "project"} <= set(by_object_type)
    assert by_object_type["bug"]["is_default_template"] is True
    assert by_object_type["task"]["is_default_template"] is True


def test_bug_default_template_matches_prd_baseline(client: TestClient):
    listed = client.get("/api/v1/workflow-definitions?object_type=bug&scope_type=system")
    assert listed.status_code == 200
    definition = next(item for item in listed.json() if item["is_default_template"] is True)

    graph = client.get(f"/api/v1/workflow-definitions/{definition['id']}")

    assert graph.status_code == 200
    states = {node["status_key"] for node in graph.json()["states"]}
    assert states == {"pending_handling", "fixing", "pending_verification", "verified", "closed"}
    transitions = {item["action_key"] for item in graph.json()["transitions"]}
    assert {
        "confirm_bug_type",
        "submit_verification",
        "verification_passed",
        "verification_failed",
        "close",
        "activate",
        "reclassify_bug_type",
    } <= transitions
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

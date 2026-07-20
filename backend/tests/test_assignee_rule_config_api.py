from uuid import uuid4

from fastapi.testclient import TestClient


def _definitions_for_config(client: TestClient, config_id: int) -> dict[str, dict]:
    response = client.get(f"/api/v1/workflow-definitions?scope_type=assignee_rule_config&scope_id={config_id}")
    assert response.status_code == 200
    return {item["object_type"]: item for item in response.json()}


def _create_draft_config(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"工作流方案-{uuid4().hex[:8]}",
            "description": "lifecycle test",
            "requirement_owner_roles": "tester",
            "task_owner_roles": "product_manager",
            "test_case_tester_roles": "tester",
            "test_run_owner_roles": "test_lead",
            "bug_owner_roles": "development_lead",
            "creation_mode": "blank",
        },
    )
    assert response.status_code == 201
    return response.json()


def _configure_core_workflows(client: TestClient, config_id: int) -> None:
    definitions = _definitions_for_config(client, config_id)
    for object_type in ("requirement", "task", "bug"):
        applied = client.post(f"/api/v1/workflow-definitions/{definitions[object_type]['id']}/apply-template")
        assert applied.status_code == 200


def test_blank_creation_builds_three_empty_draft_definitions(client: TestClient):
    config = _create_draft_config(client)

    definitions = _definitions_for_config(client, config["id"])

    assert set(definitions) == {"requirement", "task", "bug"}
    assert config["lifecycle_status"] == "draft"
    for definition in definitions.values():
        graph = client.get(f"/api/v1/workflow-definitions/{definition['id']}").json()
        assert graph["definition"]["initial_state_id"] is None
        assert graph["states"] == []
        assert graph["transitions"] == []


def test_template_sources_unify_system_and_existing_schemes(client: TestClient):
    existing = _create_draft_config(client)

    response = client.get("/api/v1/assignee-rule-configs/template-sources")

    assert response.status_code == 200
    sources = response.json()
    assert any(item["source_type"] == "system" for item in sources)
    assert any(
        item["source_type"] == "scheme" and str(item["source_id"]) == str(existing["id"])
        for item in sources
    )


def test_template_sources_exclude_legacy_schemes_missing_core_definitions(client: TestClient):
    existing = _create_draft_config(client)
    definitions = _definitions_for_config(client, existing["id"])
    for object_type in ("task", "bug"):
        deleted = client.delete(f"/api/v1/workflow-definitions/{definitions[object_type]['id']}")
        assert deleted.status_code == 204

    response = client.get("/api/v1/assignee-rule-configs/template-sources")

    assert response.status_code == 200
    assert not any(
        item["source_type"] == "scheme" and str(item["source_id"]) == str(existing["id"])
        for item in response.json()
    )


def _create_from_template(client: TestClient, source_type: str, source_id: str) -> dict:
    response = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"模板副本-{uuid4().hex[:8]}",
            "description": "independent copy",
            "creation_mode": "template",
            "template_source": {"source_type": source_type, "source_id": str(source_id)},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _normalized_graph(graph: dict) -> dict:
    state_names = {item["id"]: item["status_name"] for item in graph["states"]}

    def normalize_condition(config):
        if not isinstance(config, dict):
            return config
        normalized = dict(config)
        for field in ("routes", "target_state_id_by_owner"):
            if isinstance(normalized.get(field), dict):
                normalized[field] = {
                    key: state_names.get(value, value) for key, value in normalized[field].items()
                }
        return normalized

    return {
        "initial_state": state_names.get(graph["definition"]["initial_state_id"]),
        "states": sorted(
            [
                {key: value for key, value in item.items() if key not in {"id", "definition_id"}}
                for item in graph["states"]
            ],
            key=lambda item: (item["sort_order"], item["status_name"]),
        ),
        "transitions": sorted(
            [
                {
                    **{
                        key: value
                        for key, value in item.items()
                        if key not in {"id", "definition_id", "from_state_id", "to_state_id", "condition_config"}
                    },
                    "from_state": state_names[item["from_state_id"]],
                    "to_state": state_names[item["to_state_id"]],
                    "condition_config": normalize_condition(item.get("condition_config")),
                }
                for item in graph["transitions"]
            ],
            key=lambda item: (item["sort_order"], item["action_name"], item["from_state"], item["to_state"]),
        ),
    }


def test_system_and_existing_scheme_templates_create_independent_full_copies(client: TestClient):
    sources = client.get("/api/v1/assignee-rule-configs/template-sources").json()
    system = next(item for item in sources if item["source_type"] == "system")
    source_scheme = _create_from_template(client, "system", system["source_id"])
    copied_scheme = _create_from_template(client, "scheme", str(source_scheme["id"]))

    assert source_scheme["lifecycle_status"] == "draft"
    assert copied_scheme["lifecycle_status"] == "draft"
    assert "template_source" not in copied_scheme
    assert "source_id" not in copied_scheme

    source_definitions = _definitions_for_config(client, source_scheme["id"])
    copied_definitions = _definitions_for_config(client, copied_scheme["id"])
    assert set(source_definitions) == set(copied_definitions) == {"requirement", "task", "bug"}

    for object_type in ("requirement", "task", "bug"):
        source_graph = client.get(f"/api/v1/workflow-definitions/{source_definitions[object_type]['id']}").json()
        copied_graph = client.get(f"/api/v1/workflow-definitions/{copied_definitions[object_type]['id']}").json()

        assert source_graph["states"] and source_graph["transitions"]
        assert {item["id"] for item in source_graph["states"]}.isdisjoint(
            {item["id"] for item in copied_graph["states"]}
        )
        assert {item["id"] for item in source_graph["transitions"]}.isdisjoint(
            {item["id"] for item in copied_graph["transitions"]}
        )
        assert copied_graph["definition"]["parent_definition_id"] is None
        assert copied_graph["definition"]["template_key"] is None
        assert _normalized_graph(copied_graph) == _normalized_graph(source_graph)

    assert client.get(
        f"/api/v1/handler-transition-rules?config_id={source_scheme['id']}"
    ).status_code == 404


def test_duplicate_scheme_name_returns_conflict(client: TestClient):
    existing = _create_draft_config(client)

    duplicate = client.post(
        "/api/v1/assignee-rule-configs",
        json={"name": existing["name"], "creation_mode": "blank"},
    )

    assert duplicate.status_code == 409


def test_workflow_scheme_lifecycle_guards_project_binding_and_disable(client: TestClient):
    config = _create_draft_config(client)
    assert config["lifecycle_status"] == "draft"

    draft_binding = client.post(
        "/api/v1/projects",
        json={"name": f"Draft Scheme Project-{uuid4().hex[:8]}", "assignee_rule_config_id": config["id"]},
    )
    assert draft_binding.status_code == 409

    invalid_enable = client.post(f"/api/v1/assignee-rule-configs/{config['id']}/enable")
    assert invalid_enable.status_code == 422
    assert set(invalid_enable.json()["detail"]["invalid_object_types"]) == {"requirement", "task", "bug"}

    _configure_core_workflows(client, config["id"])
    enabled = client.post(f"/api/v1/assignee-rule-configs/{config['id']}/enable")
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["lifecycle_status"] == "enabled"

    project = client.post(
        "/api/v1/projects",
        json={"name": f"Enabled Scheme Project-{uuid4().hex[:8]}", "assignee_rule_config_id": config["id"]},
    )
    assert project.status_code == 200

    blocked = client.post(f"/api/v1/assignee-rule-configs/{config['id']}/disable")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["project_count"] == 1
    assert blocked.json()["detail"]["projects_url"].endswith(f"assignee_rule_config_id={config['id']}")

    unbound = client.patch(f"/api/v1/projects/{project.json()['id']}", json={"assignee_rule_config_id": None})
    assert unbound.status_code == 200
    disabled = client.post(f"/api/v1/assignee-rule-configs/{config['id']}/disable")
    assert disabled.status_code == 200
    assert disabled.json()["lifecycle_status"] == "disabled"

    options = client.get("/api/v1/assignee-rule-configs/project-options")
    assert options.status_code == 200
    assert config["id"] not in {item["id"] for item in options.json()}


def test_lifecycle_cannot_be_mutated_through_generic_patch(client: TestClient):
    config = _create_draft_config(client)

    response = client.patch(
        f"/api/v1/assignee-rule-configs/{config['id']}",
        json={"lifecycle_status": "enabled", "enabled": True},
    )

    assert response.status_code == 422

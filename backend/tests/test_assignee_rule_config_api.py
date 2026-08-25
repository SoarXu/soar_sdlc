from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition, WorkflowTransitionRole
from app.services import assignee_rule_config_service


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260825_001_sync_default_scheme_graphs_to_system_templates.py"
)


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
            "creation_mode": "blank",
        },
    )
    assert response.status_code == 201
    return response.json()


def _configure_core_workflows(client: TestClient, config_id: int) -> None:
    definitions = _definitions_for_config(client, config_id)
    for object_type in ("requirement", "task", "bug", "project"):
        applied = client.post(f"/api/v1/workflow-definitions/{definitions[object_type]['id']}/apply-template")
        assert applied.status_code == 200


def test_system_template_sync_migration_declares_current_revision():
    assert MIGRATION_PATH.exists()
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision = "20260825_001"' in source
    assert 'down_revision = "20260824_004"' in source
    assert "synchronize_default_scheme_graphs_to_system_templates" in source


def test_synchronize_workflow_graph_updates_target_in_place():
    with SessionLocal() as db:
        source = WorkflowDefinition(
            name=f"Sync source {uuid4().hex[:8]}",
            object_type="requirement",
            scope_type="sync_source",
            enabled=True,
        )
        target = WorkflowDefinition(
            name=f"Sync target {uuid4().hex[:8]}",
            object_type="requirement",
            scope_type="sync_target",
            enabled=True,
        )
        db.add_all([source, target])
        db.flush()
        source_start = WorkflowState(
            definition_id=source.id,
            status_name="待分派",
            category="start",
            state_role="unassigned",
            color="#111111",
            x=100,
            y=120,
            sort_order=10,
            enabled=True,
        )
        source_done = WorkflowState(
            definition_id=source.id,
            status_name="已完成",
            category="terminal",
            terminal_kind="completed",
            color="#222222",
            x=420,
            y=260,
            sort_order=20,
            enabled=True,
        )
        target_start = WorkflowState(
            definition_id=target.id,
            status_name="旧待分派",
            category="start",
            state_role="unassigned",
            color="#ffffff",
            x=0,
            y=0,
            sort_order=100,
            enabled=True,
        )
        target_done = WorkflowState(
            definition_id=target.id,
            status_name="已完成",
            category="terminal",
            terminal_kind="completed",
            color="#ffffff",
            x=0,
            y=0,
            sort_order=200,
            enabled=True,
        )
        db.add_all([source_start, source_done, target_start, target_done])
        db.flush()
        source.initial_state_id = source_start.id
        target.initial_state_id = target_start.id
        source_transition = WorkflowTransition(
            definition_id=source.id,
            action_key="complete",
            action_name="完成",
            from_state_id=source_start.id,
            to_state_id=source_done.id,
            handler_rule={"target_type": "keep_current"},
            condition_config={"field": "result", "routes": {"passed": source_done.id}},
            diagram_config={
                "version": 1,
                "routing_mode": "manual",
                "source_anchor": {"side": "bottom", "ratio": 0.5},
                "target_anchor": {"side": "top", "ratio": 0.5},
                "waypoints": [{"x": 159, "y": 180}, {"x": 479, "y": 180}],
            },
            enabled=True,
            sort_order=10,
        )
        target_transition = WorkflowTransition(
            definition_id=target.id,
            action_key="complete",
            action_name="旧完成",
            from_state_id=target_start.id,
            to_state_id=target_start.id,
            handler_rule=None,
            enabled=True,
            sort_order=99,
        )
        db.add_all([source_transition, target_transition])
        db.flush()
        db.add_all([
            WorkflowTransitionRole(transition_id=source_transition.id, role_id=101, purpose="allowed", sort_order=0),
            WorkflowTransitionRole(transition_id=target_transition.id, role_id=202, purpose="allowed", sort_order=0),
        ])
        db.commit()
        target_state_ids = {target_start.id, target_done.id}
        target_transition_id = target_transition.id
        try:
            assignee_rule_config_service.synchronize_workflow_definition_graph(db, source, target)
            db.commit()

            db.refresh(target_start)
            db.refresh(target_done)
            db.refresh(target_transition)
            assert {target_start.id, target_done.id} == target_state_ids
            assert target.initial_state_id == target_start.id
            assert (target_start.status_name, target_start.color, target_start.x, target_start.y, target_start.sort_order) == (
                "待分派", "#111111", 100, 120, 10
            )
            assert (target_done.color, target_done.x, target_done.y, target_done.sort_order) == (
                "#222222", 420, 260, 20
            )
            assert target_transition.id == target_transition_id
            assert target_transition.action_name == "完成"
            assert target_transition.to_state_id == target_done.id
            assert target_transition.condition_config == {
                "field": "result", "routes": {"passed": target_done.id}
            }
            assert target_transition.diagram_config == source_transition.diagram_config
            assert [
                (item.role_id, item.purpose, item.sort_order)
                for item in db.query(WorkflowTransitionRole)
                .filter(WorkflowTransitionRole.transition_id == target_transition.id)
                .order_by(WorkflowTransitionRole.id)
            ] == [(101, "allowed", 0)]
        finally:
            target.initial_state_id = None
            source.initial_state_id = None
            db.flush()
            db.query(WorkflowTransitionRole).filter(
                WorkflowTransitionRole.transition_id.in_([source_transition.id, target_transition.id])
            ).delete(synchronize_session=False)
            db.query(WorkflowTransition).filter(
                WorkflowTransition.id.in_([source_transition.id, target_transition.id])
            ).delete(synchronize_session=False)
            db.query(WorkflowState).filter(
                WorkflowState.id.in_([source_start.id, source_done.id, target_start.id, target_done.id])
            ).delete(synchronize_session=False)
            db.query(WorkflowDefinition).filter(
                WorkflowDefinition.id.in_([source.id, target.id])
            ).delete(synchronize_session=False)
            db.commit()


def test_synchronize_workflow_graph_adds_source_items_and_disables_removed_items():
    with SessionLocal() as db:
        source = WorkflowDefinition(
            name=f"Extensible source {uuid4().hex[:8]}",
            object_type="requirement",
            scope_type="sync_source",
            enabled=True,
        )
        target = WorkflowDefinition(
            name=f"Extensible target {uuid4().hex[:8]}",
            object_type="requirement",
            scope_type="sync_target",
            enabled=True,
        )
        db.add_all([source, target])
        db.flush()
        source_start = WorkflowState(definition_id=source.id, status_name="待分派", category="start", state_role="unassigned")
        source_done = WorkflowState(definition_id=source.id, status_name="已完成", category="terminal", terminal_kind="completed")
        source_added = WorkflowState(definition_id=source.id, status_name="待评估", category="normal", sort_order=40)
        target_start = WorkflowState(definition_id=target.id, status_name="旧待分派", category="start", state_role="unassigned")
        target_done = WorkflowState(definition_id=target.id, status_name="已完成", category="terminal", terminal_kind="completed")
        target_removed = WorkflowState(definition_id=target.id, status_name="旧状态", category="normal", sort_order=30)
        db.add_all([source_start, source_done, source_added, target_start, target_done, target_removed])
        db.flush()
        source.initial_state_id = source_start.id
        target.initial_state_id = target_start.id
        source_complete = WorkflowTransition(
            definition_id=source.id,
            action_key="complete",
            action_name="完成",
            from_state_id=source_start.id,
            to_state_id=source_done.id,
        )
        source_assess = WorkflowTransition(
            definition_id=source.id,
            action_key="assess",
            action_name="评估",
            from_state_id=source_start.id,
            to_state_id=source_added.id,
        )
        target_complete = WorkflowTransition(
            definition_id=target.id,
            action_key="complete",
            action_name="旧完成",
            from_state_id=target_start.id,
            to_state_id=target_done.id,
        )
        target_removed_transition = WorkflowTransition(
            definition_id=target.id,
            action_key="obsolete",
            action_name="旧动作",
            from_state_id=target_start.id,
            to_state_id=target_removed.id,
        )
        db.add_all([source_complete, source_assess, target_complete, target_removed_transition])
        db.commit()
        target_complete_id = target_complete.id
        try:
            assignee_rule_config_service.synchronize_workflow_definition_graph(db, source, target)
            db.commit()

            db.refresh(target_complete)
            db.refresh(target_removed)
            db.refresh(target_removed_transition)
            added_state = db.query(WorkflowState).filter(
                WorkflowState.definition_id == target.id,
                WorkflowState.status_name == "待评估",
            ).one()
            added_transition = db.query(WorkflowTransition).filter(
                WorkflowTransition.definition_id == target.id,
                WorkflowTransition.action_key == "assess",
            ).one()
            assert target_complete.id == target_complete_id
            assert target_complete.action_name == "完成"
            assert added_transition.to_state_id == added_state.id
            assert target_removed.enabled is False
            assert target_removed_transition.enabled is False
        finally:
            target.initial_state_id = None
            source.initial_state_id = None
            db.flush()
            db.query(WorkflowTransition).filter(
                WorkflowTransition.definition_id.in_([source.id, target.id])
            ).delete(synchronize_session=False)
            db.query(WorkflowState).filter(
                WorkflowState.definition_id.in_([source.id, target.id])
            ).delete(synchronize_session=False)
            db.query(WorkflowDefinition).filter(
                WorkflowDefinition.id.in_([source.id, target.id])
            ).delete(synchronize_session=False)
            db.commit()


def test_synchronize_workflow_graph_matches_duplicate_actions_by_target_state():
    with SessionLocal() as db:
        source = WorkflowDefinition(name=f"Duplicate source {uuid4().hex[:8]}", object_type="requirement", scope_type="sync_source", enabled=True)
        target = WorkflowDefinition(name=f"Duplicate target {uuid4().hex[:8]}", object_type="requirement", scope_type="sync_target", enabled=True)
        db.add_all([source, target])
        db.flush()
        source_start = WorkflowState(definition_id=source.id, status_name="待分派", category="start", state_role="unassigned")
        source_done = WorkflowState(definition_id=source.id, status_name="已完成", category="terminal", terminal_kind="completed")
        source_canceled = WorkflowState(definition_id=source.id, status_name="已取消", category="terminal", terminal_kind="terminated")
        target_start = WorkflowState(definition_id=target.id, status_name="旧待分派", category="start", state_role="unassigned")
        target_done = WorkflowState(definition_id=target.id, status_name="已完成", category="terminal", terminal_kind="completed")
        target_canceled = WorkflowState(definition_id=target.id, status_name="已取消", category="terminal", terminal_kind="terminated")
        db.add_all([source_start, source_done, source_canceled, target_start, target_done, target_canceled])
        db.flush()
        source.initial_state_id = source_start.id
        target.initial_state_id = target_start.id
        db.add_all([
            WorkflowTransition(definition_id=source.id, action_key="finish", action_name="完成", from_state_id=source_start.id, to_state_id=source_done.id, sort_order=10),
            WorkflowTransition(definition_id=source.id, action_key="finish", action_name="取消", from_state_id=source_start.id, to_state_id=source_canceled.id, sort_order=20),
        ])
        target_canceled_transition = WorkflowTransition(definition_id=target.id, action_key="finish", action_name="旧取消", from_state_id=target_start.id, to_state_id=target_canceled.id, sort_order=10)
        target_done_transition = WorkflowTransition(definition_id=target.id, action_key="finish", action_name="旧完成", from_state_id=target_start.id, to_state_id=target_done.id, sort_order=20)
        db.add_all([target_canceled_transition, target_done_transition])
        db.commit()
        try:
            assignee_rule_config_service.synchronize_workflow_definition_graph(db, source, target)
            db.commit()

            db.refresh(target_done_transition)
            db.refresh(target_canceled_transition)
            assert (target_done_transition.action_name, target_done_transition.to_state_id) == ("完成", target_done.id)
            assert (target_canceled_transition.action_name, target_canceled_transition.to_state_id) == ("取消", target_canceled.id)
        finally:
            target.initial_state_id = None
            source.initial_state_id = None
            db.flush()
            db.query(WorkflowTransition).filter(
                WorkflowTransition.definition_id.in_([source.id, target.id])
            ).delete(synchronize_session=False)
            db.query(WorkflowState).filter(
                WorkflowState.definition_id.in_([source.id, target.id])
            ).delete(synchronize_session=False)
            db.query(WorkflowDefinition).filter(
                WorkflowDefinition.id.in_([source.id, target.id])
            ).delete(synchronize_session=False)
            db.commit()


def test_synchronize_default_scheme_does_not_commit_template_initialization(monkeypatch):
    calls = []

    def ensure(db, *, reconcile_existing=True, commit=True):
        calls.append((reconcile_existing, commit))
        return []

    monkeypatch.setattr(assignee_rule_config_service, "ensure_default_workflow_templates", ensure)
    with SessionLocal() as db:
        try:
            assignee_rule_config_service.synchronize_default_scheme_graphs_to_system_templates(db)
            assert calls == [(False, False)]
        finally:
            db.rollback()


def test_blank_creation_builds_project_and_work_item_draft_definitions(client: TestClient):
    config = _create_draft_config(client)

    definitions = _definitions_for_config(client, config["id"])

    assert set(definitions) == {"requirement", "task", "bug", "project"}
    assert config["lifecycle_status"] == "draft"
    for definition in definitions.values():
        graph = client.get(f"/api/v1/workflow-definitions/{definition['id']}").json()
        assert graph["definition"]["initial_state_id"] is None
        assert graph["states"] == []
        assert graph["transitions"] == []


def test_listing_configs_recovers_only_empty_default_workflows(client: TestClient, monkeypatch):
    default_config = _create_draft_config(client)
    blank_config = _create_draft_config(client)
    monkeypatch.setitem(
        assignee_rule_config_service.DEFAULT_ASSIGNEE_RULE_CONFIG,
        "name",
        default_config["name"],
    )

    configs = client.get("/api/v1/assignee-rule-configs")

    assert configs.status_code == 200
    default_definitions = _definitions_for_config(client, default_config["id"])
    for object_type in ("requirement", "task", "bug"):
        graph = client.get(f"/api/v1/workflow-definitions/{default_definitions[object_type]['id']}").json()
        assert graph["definition"]["initial_state_id"] is not None
        assert graph["states"]
        assert graph["transitions"]

    blank_definitions = _definitions_for_config(client, blank_config["id"])
    for object_type in ("requirement", "task", "bug"):
        graph = client.get(f"/api/v1/workflow-definitions/{blank_definitions[object_type]['id']}").json()
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
    assert set(source_definitions) == set(copied_definitions) == {"requirement", "task", "bug", "project"}

    for object_type in ("requirement", "task", "bug", "project"):
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
    assert set(invalid_enable.json()["detail"]["invalid_object_types"]) == {"requirement", "task", "bug", "project"}

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

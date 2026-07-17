from app.db.session import Base
import app.models  # noqa: F401


EXPECTED_TABLES = {
    "users",
    "roles",
    "user_roles",
    "programs",
    "projects",
    "project_members",
    "iterations",
    "requirements",
    "tasks",
    "test_cases",
    "test_runs",
    "test_run_cases",
    "bugs",
    "tags",
    "object_tags",
    "attachments",
    "form_field_registry",
    "form_layout_config",
    "custom_field_value",
    "workflow_component_registry",
    "object_relation",
    "status_operation_log",
    "notifications",
    "notification_channel_config",
    "notification_delivery_log",
    "audit_log",
    "external_integration_mapping",
}


def test_prd_mysql_tables_are_registered_in_sqlalchemy_metadata():
    assert EXPECTED_TABLES <= set(Base.metadata.tables)


def test_prd_core_columns_keep_mysql_dictionary_names():
    assert "password_hash" in Base.metadata.tables["users"].columns
    assert "creator_id" in Base.metadata.tables["projects"].columns
    assert "create_time" in Base.metadata.tables["requirements"].columns
    assert "delete_time" in Base.metadata.tables["bugs"].columns


def test_workflow_state_identity_columns_are_registered_in_metadata():
    assert "initial_state_id" in Base.metadata.tables["workflow_definitions"].columns
    assert {"from_state_id", "to_state_id"} <= set(Base.metadata.tables["workflow_transitions"].columns.keys())

    for table_name in ("requirements", "tasks", "bugs"):
        assert {"workflow_definition_id", "current_state_id"} <= set(
            Base.metadata.tables[table_name].columns.keys()
        )

    assert {
        "workflow_definition_id",
        "from_state_id",
        "to_state_id",
        "from_state_name",
        "to_state_name",
    } <= set(Base.metadata.tables["status_operation_log"].columns.keys())


def test_workflow_state_identity_columns_have_foreign_keys_and_indexes():
    expected_targets = {
        ("workflow_definitions", "initial_state_id"): "workflow_states.id",
        ("workflow_transitions", "from_state_id"): "workflow_states.id",
        ("workflow_transitions", "to_state_id"): "workflow_states.id",
        ("requirements", "workflow_definition_id"): "workflow_definitions.id",
        ("requirements", "current_state_id"): "workflow_states.id",
        ("tasks", "workflow_definition_id"): "workflow_definitions.id",
        ("tasks", "current_state_id"): "workflow_states.id",
        ("bugs", "workflow_definition_id"): "workflow_definitions.id",
        ("bugs", "current_state_id"): "workflow_states.id",
        ("projects", "workflow_definition_id"): "workflow_definitions.id",
        ("projects", "current_state_id"): "workflow_states.id",
        ("iterations", "workflow_definition_id"): "workflow_definitions.id",
        ("iterations", "current_state_id"): "workflow_states.id",
    }

    for (table_name, column_name), target in expected_targets.items():
        column = Base.metadata.tables[table_name].columns[column_name]
        assert {fk.target_fullname for fk in column.foreign_keys} == {target}
        assert column.index is True


def test_project_and_iteration_workflow_identity_is_required():
    for table_name in ("projects", "iterations"):
        table = Base.metadata.tables[table_name]
        assert table.columns["workflow_definition_id"].nullable is False
        assert table.columns["current_state_id"].nullable is False


def test_workflow_identity_has_no_legacy_string_columns():
    assert "status" not in Base.metadata.tables["projects"].columns
    assert "status" not in Base.metadata.tables["iterations"].columns
    assert "status_key" not in Base.metadata.tables["workflow_states"].columns
    assert "from_status" not in Base.metadata.tables["workflow_transitions"].columns
    assert "to_status" not in Base.metadata.tables["workflow_transitions"].columns


def test_transition_state_identity_is_required():
    transition = Base.metadata.tables["workflow_transitions"]
    assert transition.columns["from_state_id"].nullable is False
    assert transition.columns["to_state_id"].nullable is False


def test_workflow_scheme_lifecycle_column_defaults_to_draft():
    column = Base.metadata.tables["assignee_rule_configs"].columns["lifecycle_status"]
    assert column.default.arg == "draft"
    assert column.nullable is False

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
    "workflow_rules",
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

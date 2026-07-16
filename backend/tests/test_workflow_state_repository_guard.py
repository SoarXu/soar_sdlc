from pathlib import Path
import re

from app.db.session import Base
import app.models  # noqa: F401


BACKEND_ROOT = Path(__file__).parents[1]


def test_core_work_items_have_no_legacy_status_column():
    for table_name in ("requirements", "tasks", "bugs"):
        assert "status" not in Base.metadata.tables[table_name].columns


def test_core_work_item_schemas_do_not_accept_or_return_status_strings():
    for relative_path in (
        "app/views/requirement_view.py",
        "app/views/task_view.py",
        "app/views/bug_view.py",
    ):
        source = (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")
        assert "Status = Literal" not in source
        assert not re.search(r"^\s+status:\s", source, flags=re.MULTILINE)


def test_core_runtime_never_writes_legacy_status_strings():
    workflow_state_source = (BACKEND_ROOT / "app/services/workflow_state_service.py").read_text(
        encoding="utf-8"
    )
    runtime_source = (BACKEND_ROOT / "app/services/workflow_runtime_service.py").read_text(
        encoding="utf-8"
    )

    assert '"status": initial_state.status_key' not in workflow_state_source
    assert "item.status = resolved_target_status" not in runtime_source
    assert 'task.status = "pending_assignment"' not in runtime_source


def test_migration_audit_script_exists_and_checks_cross_definition_references():
    source = (BACKEND_ROOT / "scripts/audit_workflow_state_migration.py").read_text(encoding="utf-8")

    assert "invalid_current_state_definition" in source
    assert "invalid_transition_definition" in source
    assert "invalid_initial_state_definition" in source

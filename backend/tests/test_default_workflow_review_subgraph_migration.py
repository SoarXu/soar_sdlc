from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260812_002_default_workflow_review_subgraphs.py"
)
MANUAL_REVIEW_MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260818_002_manual_review_workflow_templates.py"
)


def test_review_subgraph_migration_updates_recognized_existing_workflows_only():
    assert MIGRATION_PATH.exists()
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'down_revision: Union[str, None] = "20260812_001"' in source
    assert "reconcile_review_subgraph" in source
    assert "WorkflowDefinition.object_type.in_((\"requirement\", \"task\", \"bug\"))" in source


def test_manual_review_template_migration_only_updates_system_defaults():
    assert MANUAL_REVIEW_MIGRATION_PATH.exists()
    source = MANUAL_REVIEW_MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'down_revision: Union[str, None] = "20260818_001"' in source
    assert 'WorkflowDefinition.scope_type == "system"' in source
    assert 'WorkflowTransition.action_key == "submit_review"' in source
    assert "transition.trigger_config = None" in source


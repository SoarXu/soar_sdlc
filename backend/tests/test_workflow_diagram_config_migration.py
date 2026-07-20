import importlib.util
from pathlib import Path

import sqlalchemy as sa


VERSIONS = Path(__file__).parents[1] / "alembic" / "versions"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workflow_diagram_migrations_form_one_linear_chain():
    deduplicate_path = VERSIONS / "20260720_001_deduplicate_disabled_workflow_states.py"
    normalize_path = VERSIONS / "20260720_002_normalize_workflow_transition_buttons.py"
    diagram_path = VERSIONS / "20260720_003_add_workflow_transition_diagram_config.py"

    assert normalize_path.exists()
    assert diagram_path.exists()
    deduplicate = _load(deduplicate_path, "workflow_deduplicate_migration")
    normalize = _load(normalize_path, "workflow_button_normalize_migration")
    diagram = _load(diagram_path, "workflow_diagram_config_migration")

    assert deduplicate.revision == "20260720_001"
    assert normalize.revision == "20260720_002"
    assert normalize.down_revision == "20260720_001"
    assert diagram.revision == "20260720_003"
    assert diagram.down_revision == "20260720_002"


def test_diagram_upgrade_skips_column_when_bootstrap_schema_already_added_it(monkeypatch):
    diagram = _load(
        VERSIONS / "20260720_003_add_workflow_transition_diagram_config.py",
        "workflow_diagram_config_idempotence",
    )
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "CREATE TABLE workflow_transitions (id INTEGER PRIMARY KEY, diagram_config JSON NULL)"
        ))
        add_calls = []
        monkeypatch.setattr(diagram.op, "get_bind", lambda: connection)
        monkeypatch.setattr(diagram.op, "add_column", lambda *args, **kwargs: add_calls.append((args, kwargs)))

        diagram.upgrade()

    assert add_calls == []

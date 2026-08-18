from pathlib import Path

from app.db.session import Base
import app.models  # noqa: F401


def test_work_item_review_round_metadata_preserves_active_round_and_decision_audit():
    table = Base.metadata.tables["work_item_review_rounds"]

    assert {
        "object_type",
        "object_id",
        "latest_commit_id",
        "reviewer_id",
        "status",
        "active_key",
        "decision_by_id",
        "decision_at",
        "remark",
    } <= set(table.columns.keys())
    assert any(constraint.name == "uk_work_item_review_round_active" for constraint in table.constraints)
    assert table.columns["latest_commit_id"].nullable is True
    assert {"ix_work_item_review_round_reviewer_status", "ix_work_item_review_round_object_status"} <= {
        index.name for index in table.indexes
    }


def test_manual_work_item_review_migration_follows_git_review_migration():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260818_001_manual_work_item_reviews.py"
    )

    assert migration_path.exists()
    source = migration_path.read_text(encoding="utf-8")
    assert 'down_revision: Union[str, None] = "20260817_003"' in source
    assert '"work_item_review_rounds"' in source
    assert '"latest_commit_id"' in source
    assert "nullable=True" in source

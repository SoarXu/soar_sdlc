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
    assert {"ix_work_item_review_round_reviewer_status", "ix_work_item_review_round_object_status"} <= {
        index.name for index in table.indexes
    }


def test_work_item_review_round_migration_follows_the_current_head():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20260812_001_git_triggered_work_item_reviews.py"
    )

    assert migration_path.exists()
    source = migration_path.read_text(encoding="utf-8")
    assert 'down_revision: Union[str, None] = "20260811_002"' in source
    assert '"work_item_review_rounds"' in source
    assert '"uk_work_item_review_round_active"' in source

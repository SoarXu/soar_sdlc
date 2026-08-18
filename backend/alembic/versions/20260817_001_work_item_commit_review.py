"""persist commit diff retrieval state and review commit snapshots

Revision ID: 20260817_001
Revises: 20260812_003
Create Date: 2026-08-17 16:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260817_001"
down_revision: Union[str, None] = "20260812_003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "devops_commits" in inspector.get_table_names():
        commit_columns = {column["name"] for column in inspector.get_columns("devops_commits")}
        if "diff_status" not in commit_columns:
            op.add_column("devops_commits", sa.Column("diff_status", sa.String(length=32), nullable=False, server_default="pending"))
        if "diff_fetched_at" not in commit_columns:
            op.add_column("devops_commits", sa.Column("diff_fetched_at", sa.DateTime(), nullable=True))
        if "diff_error" not in commit_columns:
            op.add_column("devops_commits", sa.Column("diff_error", sa.Text(), nullable=True))

    if "work_item_review_commits" not in inspector.get_table_names():
        op.create_table(
            "work_item_review_commits",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("review_round_id", sa.BigInteger(), nullable=False),
            sa.Column("commit_id", sa.BigInteger(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("review_round_id", "commit_id", name="uk_work_item_review_commit"),
        )
        inspector = sa.inspect(bind)
    if "work_item_review_commits" in inspector.get_table_names() and not any(
        index["name"] == "ix_work_item_review_commit_round" for index in inspector.get_indexes("work_item_review_commits")
    ):
        op.create_index("ix_work_item_review_commit_round", "work_item_review_commits", ["review_round_id"])
    _backfill_legacy_review_round_snapshots(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "work_item_review_commits" in inspector.get_table_names():
        op.drop_table("work_item_review_commits")
    if "devops_commits" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("devops_commits")}
    for column_name in ("diff_error", "diff_fetched_at", "diff_status"):
        if column_name in columns:
            op.drop_column("devops_commits", column_name)


def _backfill_legacy_review_round_snapshots(bind) -> None:
    inspector = sa.inspect(bind)
    if {"work_item_review_rounds", "work_item_review_commits"} - set(inspector.get_table_names()):
        return
    rounds = sa.Table("work_item_review_rounds", sa.MetaData(), autoload_with=bind)
    snapshots = sa.Table("work_item_review_commits", sa.MetaData(), autoload_with=bind)
    for review_round_id, latest_commit_id in bind.execute(sa.select(rounds.c.id, rounds.c.latest_commit_id)):
        if latest_commit_id is None or bind.execute(
            sa.select(snapshots.c.id).where(snapshots.c.review_round_id == review_round_id, snapshots.c.commit_id == latest_commit_id)
        ).first():
            continue
        sort_order = bind.execute(
            sa.select(sa.func.coalesce(sa.func.max(snapshots.c.sort_order), -1)).where(snapshots.c.review_round_id == review_round_id)
        ).scalar_one() + 1
        bind.execute(snapshots.insert().values(review_round_id=review_round_id, commit_id=latest_commit_id, sort_order=sort_order))

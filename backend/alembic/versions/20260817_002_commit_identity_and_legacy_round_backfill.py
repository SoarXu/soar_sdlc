"""make unbound commit identity NULL-safe and backfill review snapshots

Revision ID: 20260817_002
Revises: 20260817_001
Create Date: 2026-08-17 18:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260817_002"
down_revision: Union[str, None] = "20260817_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "devops_commits" in inspector.get_table_names():
        if "repository_identity" not in {column["name"] for column in inspector.get_columns("devops_commits")}:
            op.add_column("devops_commits", sa.Column("repository_identity", sa.BigInteger(), nullable=False, server_default=sa.text("-1")))
        _backfill_repository_identity(bind)
        _replace_commit_identity_constraint(bind)
    _backfill_legacy_review_round_snapshots(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "devops_commits" not in inspector.get_table_names():
        return
    constraints = {item["name"] for item in inspector.get_unique_constraints("devops_commits")}
    if "uk_devops_commit_repository_identity_sha" in constraints:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("devops_commits") as batch:
                batch.drop_constraint("uk_devops_commit_repository_identity_sha", type_="unique")
                batch.create_unique_constraint("uk_devops_commit_repo_sha", ["provider", "repository_id", "commit_sha"])
        else:
            op.drop_constraint("uk_devops_commit_repository_identity_sha", "devops_commits", type_="unique")
            op.create_unique_constraint("uk_devops_commit_repo_sha", "devops_commits", ["provider", "repository_id", "commit_sha"])
    if "repository_identity" in {column["name"] for column in inspector.get_columns("devops_commits")}:
        op.drop_column("devops_commits", "repository_identity")


def _backfill_repository_identity(bind) -> None:
    if bind.dialect.name == "mysql":
        bind.execute(sa.text(
            "UPDATE devops_commits AS target LEFT JOIN ("
            "SELECT provider, commit_sha, MIN(id) AS canonical_id FROM ("
            "SELECT id, provider, commit_sha FROM devops_commits WHERE repository_id IS NULL"
            ") AS legacy_rows GROUP BY provider, commit_sha"
            ") AS canonical ON canonical.provider = target.provider AND canonical.commit_sha = target.commit_sha "
            "SET target.repository_identity = CASE WHEN target.repository_id IS NOT NULL THEN target.repository_id "
            "WHEN target.id = canonical.canonical_id THEN -1 ELSE -target.id END"
        ))
        return
    bind.execute(sa.text(
        "UPDATE devops_commits SET repository_identity = CASE WHEN repository_id IS NOT NULL THEN repository_id "
        "WHEN id = (SELECT MIN(candidate.id) FROM devops_commits AS candidate "
        "WHERE candidate.provider = devops_commits.provider AND candidate.commit_sha = devops_commits.commit_sha "
        "AND candidate.repository_id IS NULL) THEN -1 ELSE -id END"
    ))


def _replace_commit_identity_constraint(bind) -> None:
    inspector = sa.inspect(bind)
    constraints = {item["name"] for item in inspector.get_unique_constraints("devops_commits")}
    if "uk_devops_commit_repo_sha" in constraints:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("devops_commits") as batch:
                batch.drop_constraint("uk_devops_commit_repo_sha", type_="unique")
        else:
            op.drop_constraint("uk_devops_commit_repo_sha", "devops_commits", type_="unique")
        constraints.remove("uk_devops_commit_repo_sha")
    if "uk_devops_commit_repository_identity_sha" not in constraints:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("devops_commits") as batch:
                batch.create_unique_constraint("uk_devops_commit_repository_identity_sha", ["provider", "repository_identity", "commit_sha"])
        else:
            op.create_unique_constraint("uk_devops_commit_repository_identity_sha", "devops_commits", ["provider", "repository_identity", "commit_sha"])


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

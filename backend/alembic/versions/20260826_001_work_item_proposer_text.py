"""replace work item proposer identities with text

Revision ID: 20260826_001
Revises: 20260825_001
Create Date: 2026-08-26 00:00:00.000000
"""

import copy
import json

from alembic import op
import sqlalchemy as sa


revision = "20260826_001"
down_revision = "20260825_001"
branch_labels = None
depends_on = None

LEGACY_HANDLER_TYPES = {"proposer", "reporter", "bug_reporter"}


def _normalize_handler_rule(rule: dict) -> dict:
    normalized = copy.deepcopy(rule)
    for key in ("target_type", "fallback_type"):
        if normalized.get(key) in LEGACY_HANDLER_TYPES:
            normalized[key] = "keep_current"
    for fallback in normalized.get("fallback_chain") or []:
        if isinstance(fallback, dict) and fallback.get("type") in LEGACY_HANDLER_TYPES:
            fallback["type"] = "keep_current"
    return normalized


def _columns(table_name: str) -> set[str]:
    return {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    }


def _migrate_proposer_column(
    table_name: str,
    legacy_column: str,
) -> None:
    columns = _columns(table_name)
    if "proposer" not in columns:
        op.add_column(table_name, sa.Column("proposer", sa.Text(), nullable=True))
    if legacy_column not in columns:
        return
    op.execute(
        sa.text(
            f"UPDATE {table_name} AS item "
            f"LEFT JOIN users AS account ON account.id = item.{legacy_column} "
            "SET item.proposer = COALESCE(NULLIF(TRIM(account.full_name), ''), account.username) "
            f"WHERE item.{legacy_column} IS NOT NULL "
            "AND (item.proposer IS NULL OR TRIM(item.proposer) = '')"
        )
    )
    op.drop_column(table_name, legacy_column)


def _normalize_workflow_handler_rules() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, handler_rule FROM workflow_transitions "
            "WHERE handler_rule IS NOT NULL"
        )
    ).mappings()
    for row in rows:
        rule = row["handler_rule"]
        if isinstance(rule, str):
            rule = json.loads(rule)
        if not isinstance(rule, dict):
            continue
        normalized = _normalize_handler_rule(rule)
        if normalized != rule:
            connection.execute(
                sa.text(
                    "UPDATE workflow_transitions "
                    "SET handler_rule = :handler_rule WHERE id = :transition_id"
                ),
                {
                    "handler_rule": json.dumps(normalized, ensure_ascii=False),
                    "transition_id": row["id"],
                },
            )


def upgrade() -> None:
    _migrate_proposer_column("requirements", "proposer_id")
    _migrate_proposer_column("bugs", "reporter_id")
    op.execute(
        sa.text(
            "UPDATE workflow_transitions SET allowed_roles = NULLIF("
            "TRIM(BOTH ',' FROM REPLACE(REPLACE(REPLACE(REPLACE("
            "CONCAT(',', COALESCE(allowed_roles, ''), ','), "
            "',reporter,', ','), ',proposer,', ','), ',bug_reporter,', ','), ',,', ',')), '') "
            "WHERE FIND_IN_SET('reporter', allowed_roles) "
            "OR FIND_IN_SET('proposer', allowed_roles) "
            "OR FIND_IN_SET('bug_reporter', allowed_roles)"
        )
    )
    _normalize_workflow_handler_rules()


def downgrade() -> None:
    op.add_column("requirements", sa.Column("proposer_id", sa.BigInteger(), nullable=True))
    op.add_column("bugs", sa.Column("reporter_id", sa.BigInteger(), nullable=True))
    op.drop_column("requirements", "proposer")
    op.drop_column("bugs", "proposer")

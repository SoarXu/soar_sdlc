"""remove empty legacy trigger from the default Bug workflow

Revision ID: 20260729_002
Revises: 20260729_001
Create Date: 2026-07-29 12:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_002"
down_revision: Union[str, None] = "20260729_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TRANSITIONS = sa.table(
    "workflow_transitions",
    sa.column("id", sa.BigInteger),
    sa.column("definition_id", sa.BigInteger),
    sa.column("trigger_config", sa.JSON),
)


def _remove_legacy_bug_trigger_statement(dialect_name: str = "sqlite"):
    if dialect_name == "sqlite":
        where_clause = """
            id = 136
            AND definition_id = 33
            AND json_type(trigger_config) = 'object'
            AND (SELECT count(*) FROM json_each(trigger_config)) = 1
            AND json_extract(trigger_config, '$.type') = 'legacy_script'
        """
    elif dialect_name in {"mysql", "mariadb"}:
        where_clause = """
            id = 136
            AND definition_id = 33
            AND JSON_TYPE(trigger_config) = 'OBJECT'
            AND JSON_LENGTH(trigger_config) = 1
            AND JSON_UNQUOTE(JSON_EXTRACT(trigger_config, '$.type')) = 'legacy_script'
        """
    else:
        raise RuntimeError(f"Unsupported database dialect: {dialect_name}")

    return sa.text(f"""
        UPDATE workflow_transitions
        SET trigger_config = NULL
        WHERE {where_clause}
    """)


def upgrade() -> None:
    op.execute(_remove_legacy_bug_trigger_statement(op.get_bind().dialect.name))


def downgrade() -> None:
    # The marker has no payload, so its previous value cannot be recovered.
    pass

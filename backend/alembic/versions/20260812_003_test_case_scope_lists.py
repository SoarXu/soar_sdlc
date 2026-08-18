"""add test-case scope lists

Revision ID: 20260812_003
Revises: 20260812_002
Create Date: 2026-08-18 12:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_003"
down_revision: Union[str, None] = "20260812_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("test_cases")}
    if "test_scopes" not in columns:
        op.add_column("test_cases", sa.Column("test_scopes", sa.JSON(), nullable=True))
    bind.execute(
        sa.text(
            "UPDATE test_cases SET test_scopes = JSON_ARRAY(test_scope) "
            "WHERE test_scopes IS NULL AND test_scope IS NOT NULL"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("test_cases")}
    if "test_scopes" in columns:
        op.drop_column("test_cases", "test_scopes")

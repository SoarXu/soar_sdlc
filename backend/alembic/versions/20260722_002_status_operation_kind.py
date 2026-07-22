"""separate state and iteration membership operations

Revision ID: 20260722_002
Revises: 20260722_001
Create Date: 2026-07-22 16:30:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260722_002"
down_revision: Union[str, None] = "20260722_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("status_operation_log")}
    if "operation_kind" not in columns:
        op.add_column(
            "status_operation_log",
            sa.Column("operation_kind", sa.String(length=16), nullable=False, server_default="state"),
        )
    op.execute(
        "UPDATE status_operation_log SET operation_kind = 'membership' "
        "WHERE action LIKE 'iteration\\_%'"
    )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("status_operation_log")}
    if "operation_kind" in columns:
        op.drop_column("status_operation_log", "operation_kind")

"""add workflow transition diagram configuration

Revision ID: 20260720_003
Revises: 20260720_002
Create Date: 2026-07-20 22:45:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260720_003"
down_revision: Union[str, None] = "20260720_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("workflow_transitions")}
    if "diagram_config" in columns:
        return
    op.add_column(
        "workflow_transitions",
        sa.Column("diagram_config", sa.JSON(), nullable=True, comment="diagram routing config"),
    )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("workflow_transitions")}
    if "diagram_config" in columns:
        op.drop_column("workflow_transitions", "diagram_config")

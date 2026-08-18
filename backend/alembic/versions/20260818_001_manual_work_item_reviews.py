"""allow manual work-item review rounds without a Git commit

Revision ID: 20260818_001
Revises: 20260817_003
Create Date: 2026-08-18 23:45:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260818_001"
down_revision: Union[str, None] = "20260817_003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "work_item_review_rounds" not in sa.inspect(bind).get_table_names():
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("work_item_review_rounds") as batch_op:
            batch_op.alter_column("latest_commit_id", existing_type=sa.BigInteger(), nullable=True)
        return
    op.alter_column(
        "work_item_review_rounds",
        "latest_commit_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )


def downgrade() -> None:
    # Existing manual rounds cannot be safely converted to a required commit reference.
    pass

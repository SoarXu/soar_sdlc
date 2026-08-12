"""add rich-text steps content and expand test-case rich fields

Revision ID: 20260811_001
Revises: 20260810_001
Create Date: 2026-08-11 15:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "20260811_001"
down_revision: Union[str, None] = "20260810_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("test_cases")}
    is_mysql = bind.dialect.name in {"mysql", "mariadb"}
    rich_type = mysql.MEDIUMTEXT() if is_mysql else sa.Text()

    if "steps_content" not in columns:
        op.add_column("test_cases", sa.Column("steps_content", rich_type, nullable=True))
    elif is_mysql:
        op.alter_column("test_cases", "steps_content", existing_type=sa.Text(), type_=rich_type, existing_nullable=True)

    if is_mysql:
        op.alter_column("test_cases", "precondition", existing_type=sa.Text(), type_=rich_type, existing_nullable=True)
        op.alter_column("test_cases", "expected_result", existing_type=sa.Text(), type_=rich_type, existing_nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("test_cases")}
    if bind.dialect.name in {"mysql", "mariadb"}:
        op.alter_column("test_cases", "precondition", existing_type=mysql.MEDIUMTEXT(), type_=sa.Text(), existing_nullable=True)
        op.alter_column("test_cases", "expected_result", existing_type=mysql.MEDIUMTEXT(), type_=sa.Text(), existing_nullable=True)
    if "steps_content" in columns:
        op.drop_column("test_cases", "steps_content")

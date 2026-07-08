"""workbench workflow default template schema

Revision ID: 20260709_001
Revises: 20260625_004
Create Date: 2026-07-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260709_001"
down_revision: Union[str, None] = "20260625_004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "object_watch" not in inspector.get_table_names():
        op.create_table(
            "object_watch",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("object_type", sa.String(length=64), nullable=False),
            sa.Column("object_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "update_time",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("idx_object_watch_object", "object_watch", ["object_type", "object_id"])
        op.create_index("idx_object_watch_user", "object_watch", ["user_id", "enabled"])

    if "work_item_comments" not in inspector.get_table_names():
        op.create_table(
            "work_item_comments",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("object_type", sa.String(length=64), nullable=False),
            sa.Column("object_id", sa.BigInteger(), nullable=False),
            sa.Column("author_id", sa.BigInteger(), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("mentioned_user_ids", sa.JSON(), nullable=True),
            sa.Column("mentions_metadata", sa.JSON(), nullable=True),
            sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column(
                "update_time",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("idx_work_item_comments_object", "work_item_comments", ["object_type", "object_id"])
        op.create_index("idx_work_item_comments_author", "work_item_comments", ["author_id"])

    workflow_definition_columns = _column_names("workflow_definitions")
    if "template_key" not in workflow_definition_columns:
        op.add_column("workflow_definitions", sa.Column("template_key", sa.String(length=64), nullable=True))
        op.create_index("idx_wfd_template_key", "workflow_definitions", ["template_key"])
    if "parent_definition_id" not in workflow_definition_columns:
        op.add_column("workflow_definitions", sa.Column("parent_definition_id", sa.BigInteger(), nullable=True))
        op.create_index("idx_wfd_parent_definition_id", "workflow_definitions", ["parent_definition_id"])
    if "is_default_template" not in workflow_definition_columns:
        op.add_column(
            "workflow_definitions",
            sa.Column("is_default_template", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )

    notification_columns = _column_names("notifications")
    if "category" not in notification_columns:
        op.add_column("notifications", sa.Column("category", sa.String(length=32), nullable=False, server_default="system"))
    if "source_type" not in notification_columns:
        op.add_column("notifications", sa.Column("source_type", sa.String(length=64), nullable=True))
    if "source_id" not in notification_columns:
        op.add_column("notifications", sa.Column("source_id", sa.BigInteger(), nullable=True))
    if "metadata_json" not in notification_columns:
        op.add_column("notifications", sa.Column("metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    pass

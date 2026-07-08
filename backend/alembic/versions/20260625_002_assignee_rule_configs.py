"""add assignee rule configs

Revision ID: 20260625_002
Revises: 20260625_001
Create Date: 2026-06-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260625_002"
down_revision: Union[str, None] = "20260625_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if not inspector.has_table("assignee_rule_configs"):
        op.create_table(
            "assignee_rule_configs",
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False, comment="配置名称"),
            sa.Column("description", sa.Text(), nullable=True, comment="配置说明"),
            sa.Column("requirement_owner_roles", sa.String(length=255), nullable=False, server_default="", comment="需求负责人角色"),
            sa.Column("task_owner_roles", sa.String(length=255), nullable=False, server_default="", comment="任务负责人角色"),
            sa.Column("test_case_tester_roles", sa.String(length=255), nullable=False, server_default="", comment="用例测试人角色"),
            sa.Column("test_run_owner_roles", sa.String(length=255), nullable=False, server_default="", comment="测试单负责人角色"),
            sa.Column("bug_owner_roles", sa.String(length=255), nullable=False, server_default="", comment="Bug负责人角色"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
            sa.Column("create_time", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column(
                "update_time",
                sa.DateTime(),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                server_onupdate=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uk_assignee_rule_configs_name"),
            comment="责任人规则配置",
        )
        op.create_index(op.f("ix_assignee_rule_configs_id"), "assignee_rule_configs", ["id"], unique=False)
    project_columns = {column["name"] for column in inspector.get_columns("projects")}
    if "assignee_rule_config_id" not in project_columns:
        op.add_column("projects", sa.Column("assignee_rule_config_id", sa.BigInteger(), nullable=True, comment="责任人规则配置ID"))

    existing = connection.execute(
        sa.text("select id from assignee_rule_configs where name = :name"),
        {"name": "默认责任人规则"},
    ).first()
    if not existing:
        op.execute(
            """
            insert into assignee_rule_configs (
                name,
                description,
                requirement_owner_roles,
                task_owner_roles,
                test_case_tester_roles,
                test_run_owner_roles,
                bug_owner_roles,
                enabled
            )
            values (
                '默认责任人规则',
                '按当前系统默认团队角色分配责任人',
                'developer',
                'developer',
                'tester',
                'tester',
                'developer',
                1
            )
            """
        )


def downgrade() -> None:
    op.drop_column("projects", "assignee_rule_config_id")
    op.drop_index(op.f("ix_assignee_rule_configs_id"), table_name="assignee_rule_configs")
    op.drop_table("assignee_rule_configs")

"""restore multi assignee rules

Revision ID: 20260625_004
Revises: 20260625_003
Create Date: 2026-06-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260625_004"
down_revision: Union[str, None] = "20260625_003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    exists = connection.execute(
        sa.text("select id from assignee_rule_configs where name = :name"),
        {"name": "默认责任人规则"},
    ).first()
    if exists:
        return
    connection.execute(
        sa.text(
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
    )


def downgrade() -> None:
    pass

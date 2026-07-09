"""translate default workflow templates to zh-CN

Revision ID: 20260709_002
Revises: 20260709_001
Create Date: 2026-07-09 00:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260709_002"
down_revision: Union[str, None] = "20260709_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TEMPLATE_NAME_MAP = {
    "requirement.default": "默认需求工作流模板",
    "task.default": "默认任务工作流模板",
    "bug.default": "默认缺陷工作流模板",
    "iteration.default": "默认迭代工作流模板",
    "project.default": "默认项目工作流模板",
}

STATE_NAME_MAP = {
    "requirement.default": {
        "pending_assignment": "待分派",
        "in_processing": "处理中",
        "pending_confirmation": "待确认",
        "completed": "已完成",
        "canceled": "已取消",
    },
    "task.default": {
        "pending_assignment": "待分派",
        "in_processing": "处理中",
        "pending_confirmation": "待确认",
        "completed": "已完成",
        "canceled": "已取消",
    },
    "bug.default": {
        "pending_handling": "待处理",
        "fixing": "修复中",
        "pending_verification": "待验证",
        "verified": "已验证",
        "closed": "已关闭",
    },
    "iteration.default": {
        "planning": "规划中",
        "active": "进行中",
        "completed": "已完成",
        "canceled": "已取消",
    },
    "project.default": {
        "planning": "规划中",
        "active": "进行中",
        "paused": "已暂停",
        "closed": "已关闭",
    },
}

TRANSITION_NAME_MAP = {
    "requirement.default": {
        "claim": "认领",
        "assign": "指派",
        "complete": "完成",
        "cancel": "取消",
        "reactivate": "重新激活",
    },
    "task.default": {
        "claim": "认领",
        "assign": "指派",
        "complete": "完成",
        "submit_confirmation": "提交确认",
        "approve_confirmation": "确认通过",
        "return_rework": "退回返工",
        "cancel": "取消",
        "reactivate": "重新激活",
    },
    "bug.default": {
        "confirm_bug_type": "确认缺陷类型",
        "reclassify_bug_type": "重新判定缺陷类型",
        "submit_verification": "提交验证",
        "verification_passed": "验证通过",
        "verification_failed": "验证不通过",
        "close": "关闭",
        "activate": "激活",
    },
    "iteration.default": {
        "start": "开始",
        "complete": "完成",
        "cancel": "取消",
    },
    "project.default": {
        "start": "开始",
        "suspend": "暂停",
        "resume": "恢复",
        "close": "关闭",
    },
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if {"workflow_definitions", "workflow_states", "workflow_transitions"} - tables:
        return

    definition_rows = bind.execute(
        sa.text(
            """
            SELECT id, template_key
            FROM workflow_definitions
            WHERE scope_type = :scope_type
              AND COALESCE(is_default_template, 0) = 1
            """
        ),
        {"scope_type": "system"},
    ).fetchall()

    for definition_id, template_key in definition_rows:
        if template_key not in TEMPLATE_NAME_MAP:
            continue

        bind.execute(
            sa.text(
                """
                UPDATE workflow_definitions
                SET name = :name,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = :definition_id
                """
            ),
            {"definition_id": definition_id, "name": TEMPLATE_NAME_MAP[template_key]},
        )

        for status_key, status_name in STATE_NAME_MAP.get(template_key, {}).items():
            bind.execute(
                sa.text(
                    """
                    UPDATE workflow_states
                    SET status_name = :status_name,
                        update_time = CURRENT_TIMESTAMP
                    WHERE definition_id = :definition_id
                      AND status_key = :status_key
                    """
                ),
                {
                    "definition_id": definition_id,
                    "status_key": status_key,
                    "status_name": status_name,
                },
            )

        for action_key, action_name in TRANSITION_NAME_MAP.get(template_key, {}).items():
            bind.execute(
                sa.text(
                    """
                    UPDATE workflow_transitions
                    SET action_name = :action_name,
                        update_time = CURRENT_TIMESTAMP
                    WHERE definition_id = :definition_id
                      AND action_key = :action_key
                    """
                ),
                {
                    "definition_id": definition_id,
                    "action_key": action_key,
                    "action_name": action_name,
                },
            )


def downgrade() -> None:
    pass

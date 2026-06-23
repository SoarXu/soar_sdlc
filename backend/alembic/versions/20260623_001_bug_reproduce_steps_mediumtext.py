"""Expand bug reproduce steps for rich text images.

Revision ID: 20260623_001
Revises: 20260611_002
Create Date: 2026-06-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260623_001"
down_revision = "20260611_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "bugs",
        "reproduce_steps",
        existing_type=sa.Text(),
        type_=mysql.MEDIUMTEXT(),
        existing_nullable=True,
        existing_comment="复现步骤",
        comment="复现步骤，支持富文本和粘贴图片",
    )


def downgrade() -> None:
    op.alter_column(
        "bugs",
        "reproduce_steps",
        existing_type=mysql.MEDIUMTEXT(),
        type_=sa.Text(),
        existing_nullable=True,
        existing_comment="复现步骤，支持富文本和粘贴图片",
        comment="复现步骤",
    )

"""add status column to knowledge_qa_history

Revision ID: 20260528_kqa_status
Revises: 20260528_kqa_history
Create Date: 2026-05-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260528_kqa_status"
down_revision: Union[str, None] = "20260528_kqa_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_qa_history",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="completed",
            comment="completed / partial / cancelled / timeout / error",
        ),
    )
    op.create_index("idx_kqa_history_status", "knowledge_qa_history", ["status"])


def downgrade() -> None:
    op.drop_index("idx_kqa_history_status", table_name="knowledge_qa_history")
    op.drop_column("knowledge_qa_history", "status")

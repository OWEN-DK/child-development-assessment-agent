"""add knowledge_qa_history table

Revision ID: 20260528_kqa_history
Revises: None
Create Date: 2026-05-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260528_kqa_history"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_qa_history",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("task_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("result_json", sa.JSON, nullable=False, comment="完整的问答结果"),
        sa.Column("matched_books_json", sa.JSON, nullable=True, comment="匹配到的书籍列表"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), index=True),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
    )
    op.create_index("idx_kqa_history_task_id", "knowledge_qa_history", ["task_id"])
    op.create_index("idx_kqa_history_created_at", "knowledge_qa_history", ["created_at"])


def downgrade() -> None:
    op.drop_table("knowledge_qa_history")

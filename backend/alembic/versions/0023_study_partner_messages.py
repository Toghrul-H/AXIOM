"""Add private Study Partner chat messages.

Revision ID: 0023
Revises: 0022
"""

from alembic import op
import sqlalchemy as sa


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "study_partner_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("study_partner_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(content) >= 1 AND length(content) <= 2000", name="ck_study_partner_messages_content_length"),
    )
    op.create_index("ix_study_partner_messages_request_id", "study_partner_messages", ["request_id"])
    op.create_index("ix_study_partner_messages_sender_user_id", "study_partner_messages", ["sender_user_id"])
    op.create_index("ix_study_partner_messages_request_created", "study_partner_messages", ["request_id", "created_at", "id"])


def downgrade():
    op.drop_index("ix_study_partner_messages_request_created", table_name="study_partner_messages")
    op.drop_index("ix_study_partner_messages_sender_user_id", table_name="study_partner_messages")
    op.drop_index("ix_study_partner_messages_request_id", table_name="study_partner_messages")
    op.drop_table("study_partner_messages")

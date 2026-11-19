"""Add persistent Study Partner chat receipts.

Revision ID: 0032
Revises: 0031
"""

from alembic import op
import sqlalchemy as sa


revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "study_partner_chat_receipts",
        sa.Column(
            "request_id",
            sa.Integer(),
            sa.ForeignKey("study_partner_requests.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "last_read_message_id",
            sa.Integer(),
            sa.ForeignKey("study_partner_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("typing_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_study_partner_chat_receipts_user",
        "study_partner_chat_receipts",
        ["user_id"],
    )
    op.create_index(
        "ix_study_partner_chat_receipts_typing_expires",
        "study_partner_chat_receipts",
        ["typing_expires_at"],
    )


def downgrade():
    op.drop_index(
        "ix_study_partner_chat_receipts_typing_expires",
        table_name="study_partner_chat_receipts",
    )
    op.drop_index(
        "ix_study_partner_chat_receipts_user",
        table_name="study_partner_chat_receipts",
    )
    op.drop_table("study_partner_chat_receipts")

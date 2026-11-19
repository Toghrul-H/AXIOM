"""Add Study Partner message replies and reactions.

Revision ID: 0031
Revises: 0030
"""

from alembic import op
import sqlalchemy as sa


revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "study_partner_messages",
        sa.Column(
            "reply_to_message_id",
            sa.Integer(),
            sa.ForeignKey("study_partner_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_study_partner_messages_reply_to_message_id",
        "study_partner_messages",
        ["reply_to_message_id"],
    )
    op.create_table(
        "study_partner_message_reactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("study_partner_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("emoji", sa.String(length=8), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "emoji IN ('👍', '❤️', '😂', '😮', '😢', '🎉')",
            name="ck_study_partner_message_reactions_emoji",
        ),
        sa.UniqueConstraint(
            "message_id",
            "user_id",
            "emoji",
            name="uq_study_partner_message_reactions_user_emoji",
        ),
    )
    op.create_index(
        "ix_study_partner_message_reactions_message",
        "study_partner_message_reactions",
        ["message_id"],
    )


def downgrade():
    op.drop_index(
        "ix_study_partner_message_reactions_message",
        table_name="study_partner_message_reactions",
    )
    op.drop_table("study_partner_message_reactions")
    op.drop_index(
        "ix_study_partner_messages_reply_to_message_id",
        table_name="study_partner_messages",
    )
    op.drop_column("study_partner_messages", "reply_to_message_id")

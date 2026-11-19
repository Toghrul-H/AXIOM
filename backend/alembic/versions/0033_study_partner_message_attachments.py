"""Add private Study Partner chat attachments.

Revision ID: 0033
Revises: 0032
"""

from alembic import op
import sqlalchemy as sa


revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade():
    # Attachment-only messages are allowed; API validation still requires text
    # or at least one attachment.
    op.drop_constraint(
        "ck_study_partner_messages_content_length",
        "study_partner_messages",
        type_="check",
    )
    op.create_check_constraint(
        "ck_study_partner_messages_content_length",
        "study_partner_messages",
        "length(content) <= 2000",
    )
    op.create_table(
        "study_partner_message_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "request_id",
            sa.Integer(),
            sa.ForeignKey("study_partner_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("study_partner_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "uploader_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(length=180), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False, unique=True),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "size_bytes > 0", name="ck_study_partner_message_attachments_size"
        ),
        sa.CheckConstraint(
            "length(sha256) = 64",
            name="ck_study_partner_message_attachments_sha256",
        ),
    )
    op.create_index(
        "ix_study_partner_message_attachments_request",
        "study_partner_message_attachments",
        ["request_id"],
    )
    op.create_index(
        "ix_study_partner_message_attachments_message",
        "study_partner_message_attachments",
        ["message_id"],
    )


def downgrade():
    op.drop_index(
        "ix_study_partner_message_attachments_message",
        table_name="study_partner_message_attachments",
    )
    op.drop_index(
        "ix_study_partner_message_attachments_request",
        table_name="study_partner_message_attachments",
    )
    op.drop_table("study_partner_message_attachments")
    op.drop_constraint(
        "ck_study_partner_messages_content_length",
        "study_partner_messages",
        type_="check",
    )
    op.create_check_constraint(
        "ck_study_partner_messages_content_length",
        "study_partner_messages",
        "length(content) >= 1 AND length(content) <= 2000",
    )

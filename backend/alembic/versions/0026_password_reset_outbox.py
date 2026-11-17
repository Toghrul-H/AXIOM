"""Add encrypted durable delivery work for password resets.

Revision ID: 0026
Revises: 0025
"""

from alembic import op
import sqlalchemy as sa


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "password_reset_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_ciphertext", sa.String(length=512), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.String(length=64), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_category", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("attempts >= 0", name="ck_password_reset_outbox_attempts"),
        sa.UniqueConstraint("user_id", name="uq_password_reset_outbox_user_id"),
    )
    op.create_index("ix_password_reset_outbox_available_at", "password_reset_outbox", ["available_at"])
    op.create_index("ix_password_reset_outbox_expires_at", "password_reset_outbox", ["expires_at"])
    op.create_index("ix_password_reset_outbox_claim_token", "password_reset_outbox", ["claim_token"])


def downgrade():
    op.drop_index("ix_password_reset_outbox_claim_token", table_name="password_reset_outbox")
    op.drop_index("ix_password_reset_outbox_expires_at", table_name="password_reset_outbox")
    op.drop_index("ix_password_reset_outbox_available_at", table_name="password_reset_outbox")
    op.drop_table("password_reset_outbox")

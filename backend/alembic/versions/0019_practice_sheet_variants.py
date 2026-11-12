"""Add staff practice sheets and immutable question-set variants.

Revision ID: 0019
Revises: 0018
"""
from alembic import op
import sqlalchemy as sa


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "practice_sheets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="draft"),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft','finalized')", name="ck_practice_sheets_status"),
    )
    op.create_index("ix_practice_sheets_status", "practice_sheets", ["status"])
    op.create_index("ix_practice_sheets_created_by_id", "practice_sheets", ["created_by_id"])
    op.create_table(
        "practice_sheet_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("practice_sheet_id", sa.Integer(), sa.ForeignKey("practice_sheets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.UniqueConstraint("practice_sheet_id", "question_id", name="uq_practice_sheet_questions_question"),
        sa.UniqueConstraint("practice_sheet_id", "position", name="uq_practice_sheet_questions_position"),
        sa.CheckConstraint("position >= 0", name="ck_practice_sheet_questions_position"),
        sa.CheckConstraint("points IS NULL OR (points > 0 AND points <= 1000)", name="ck_practice_sheet_questions_points"),
    )
    op.create_index("ix_practice_sheet_questions_practice_sheet_id", "practice_sheet_questions", ["practice_sheet_id"])
    op.create_index("ix_practice_sheet_questions_question_id", "practice_sheet_questions", ["question_id"])
    op.create_table(
        "practice_sheet_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("practice_sheet_id", sa.Integer(), sa.ForeignKey("practice_sheets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(length=16), nullable=False),
        sa.Column("question_snapshot", sa.JSON(), nullable=False),
        sa.Column("seed", sa.String(length=120), nullable=False),
        sa.Column("generator_version", sa.String(length=40), nullable=False, server_default="question-set-v1"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("practice_sheet_id", "label", name="uq_practice_sheet_variants_label"),
    )
    op.create_index("ix_practice_sheet_variants_practice_sheet_id", "practice_sheet_variants", ["practice_sheet_id"])


def downgrade():
    op.drop_index("ix_practice_sheet_variants_practice_sheet_id", table_name="practice_sheet_variants")
    op.drop_table("practice_sheet_variants")
    op.drop_index("ix_practice_sheet_questions_question_id", table_name="practice_sheet_questions")
    op.drop_index("ix_practice_sheet_questions_practice_sheet_id", table_name="practice_sheet_questions")
    op.drop_table("practice_sheet_questions")
    op.drop_index("ix_practice_sheets_created_by_id", table_name="practice_sheets")
    op.drop_index("ix_practice_sheets_status", table_name="practice_sheets")
    op.drop_table("practice_sheets")

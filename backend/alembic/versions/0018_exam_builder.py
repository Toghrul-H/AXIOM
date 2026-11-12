"""Add Exam Builder persistence and immutable final snapshots.

Revision ID: 0018
Revises: 0017
"""
from alembic import op
import sqlalchemy as sa


revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "exams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="draft"),
        sa.Column("assessment_configuration_id", sa.Integer(), sa.ForeignKey("assessment_configurations.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("question_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft','finalized')", name="ck_exams_status"),
        sa.CheckConstraint("(status = 'draft' AND finalized_at IS NULL AND question_snapshot IS NULL) OR (status = 'finalized' AND finalized_at IS NOT NULL AND question_snapshot IS NOT NULL)", name="ck_exams_finalization_snapshot"),
    )
    op.create_index("ix_exams_status", "exams", ["status"])
    op.create_index("ix_exams_assessment_configuration_id", "exams", ["assessment_configuration_id"])
    op.create_index("ix_exams_created_by_id", "exams", ["created_by_id"])
    op.create_table(
        "exam_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.UniqueConstraint("exam_id", "question_id", name="uq_exam_questions_question"),
        sa.UniqueConstraint("exam_id", "position", name="uq_exam_questions_position"),
        sa.CheckConstraint("position >= 0", name="ck_exam_questions_position"),
        sa.CheckConstraint("points > 0 AND points <= 1000", name="ck_exam_questions_points"),
    )
    op.create_index("ix_exam_questions_exam_id", "exam_questions", ["exam_id"])
    op.create_index("ix_exam_questions_question_id", "exam_questions", ["question_id"])


def downgrade():
    op.drop_index("ix_exam_questions_question_id", table_name="exam_questions")
    op.drop_index("ix_exam_questions_exam_id", table_name="exam_questions")
    op.drop_table("exam_questions")
    op.drop_index("ix_exams_created_by_id", table_name="exams")
    op.drop_index("ix_exams_assessment_configuration_id", table_name="exams")
    op.drop_index("ix_exams_status", table_name="exams")
    op.drop_table("exams")

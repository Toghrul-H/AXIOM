"""Add custom demonstrator application questionnaires.

Revision ID: 0017
Revises: 0016
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("demonstrator_applications", sa.Column("lecture_grade", sa.String(20), nullable=True))
    op.add_column("demonstrator_applications", sa.Column("practice_grade", sa.String(20), nullable=True))
    op.add_column("demonstrator_applications", sa.Column("weekly_availability", sa.Integer(), nullable=True))
    op.add_column("demonstrator_applications", sa.Column("preferred_responsibilities", sa.JSON(), nullable=True))
    op.create_table(
        "demonstrator_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("demonstrator_vacancies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(24), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("vacancy_id", "display_order", name="uq_demonstrator_question_order"),
    )
    op.create_index("ix_demonstrator_questions_vacancy_id", "demonstrator_questions", ["vacancy_id"])
    op.create_table(
        "demonstrator_application_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("demonstrator_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("demonstrator_questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("question_title", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(24), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("application_id", "question_id", name="uq_demonstrator_application_answer"),
    )
    op.create_index("ix_demonstrator_application_answers_application_id", "demonstrator_application_answers", ["application_id"])
    op.create_index("ix_demonstrator_application_answers_question_id", "demonstrator_application_answers", ["question_id"])


def downgrade():
    op.drop_index("ix_demonstrator_application_answers_question_id", table_name="demonstrator_application_answers")
    op.drop_index("ix_demonstrator_application_answers_application_id", table_name="demonstrator_application_answers")
    op.drop_table("demonstrator_application_answers")
    op.drop_index("ix_demonstrator_questions_vacancy_id", table_name="demonstrator_questions")
    op.drop_table("demonstrator_questions")
    op.drop_column("demonstrator_applications", "preferred_responsibilities")
    op.drop_column("demonstrator_applications", "weekly_availability")
    op.drop_column("demonstrator_applications", "practice_grade")
    op.drop_column("demonstrator_applications", "lecture_grade")

"""Add staff-authored course chapters and lessons.

Revision ID: 0024
Revises: 0023
"""

from alembic import op
import sqlalchemy as sa


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "course_chapters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_course_chapters_slug"),
        sa.UniqueConstraint("position", name="uq_course_chapters_position"),
        sa.CheckConstraint("position >= 0", name="ck_course_chapters_position"),
        sa.CheckConstraint("status IN ('draft', 'published')", name="ck_course_chapters_status"),
    )
    op.create_index("ix_course_chapters_status", "course_chapters", ["status"])
    op.create_table(
        "course_lessons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("course_chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("chapter_id", "slug", name="uq_course_lessons_chapter_slug"),
        sa.UniqueConstraint("chapter_id", "position", name="uq_course_lessons_chapter_position"),
        sa.CheckConstraint("position >= 0", name="ck_course_lessons_position"),
        sa.CheckConstraint("status IN ('draft', 'published')", name="ck_course_lessons_status"),
    )
    op.create_index("ix_course_lessons_chapter_id", "course_lessons", ["chapter_id"])
    op.create_index("ix_course_lessons_status", "course_lessons", ["status"])
    op.create_table(
        "course_lesson_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("lesson_id", "question_id", name="uq_course_lesson_questions_question"),
        sa.UniqueConstraint("lesson_id", "position", name="uq_course_lesson_questions_position"),
        sa.CheckConstraint("position >= 0", name="ck_course_lesson_questions_position"),
    )
    op.create_index("ix_course_lesson_questions_lesson_id", "course_lesson_questions", ["lesson_id"])
    op.create_index("ix_course_lesson_questions_question_id", "course_lesson_questions", ["question_id"])


def downgrade():
    op.drop_index("ix_course_lesson_questions_question_id", table_name="course_lesson_questions")
    op.drop_index("ix_course_lesson_questions_lesson_id", table_name="course_lesson_questions")
    op.drop_table("course_lesson_questions")
    op.drop_index("ix_course_lessons_status", table_name="course_lessons")
    op.drop_index("ix_course_lessons_chapter_id", table_name="course_lessons")
    op.drop_table("course_lessons")
    op.drop_index("ix_course_chapters_status", table_name="course_chapters")
    op.drop_table("course_chapters")

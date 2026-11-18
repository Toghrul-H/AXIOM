"""Add private course-material metadata placeholders.

Revision ID: 0028
Revises: 0027
"""

from alembic import op
import sqlalchemy as sa


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "course_materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("course_chapters.id", ondelete="CASCADE"), nullable=True),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True, unique=True),
        sa.Column("media_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="draft"),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("position >= 0", name="ck_course_materials_position"),
        sa.CheckConstraint("status IN ('draft', 'published')", name="ck_course_materials_status"),
        sa.CheckConstraint(
            "(chapter_id IS NOT NULL AND lesson_id IS NULL) OR (chapter_id IS NULL AND lesson_id IS NOT NULL)",
            name="ck_course_materials_exactly_one_parent",
        ),
        sa.CheckConstraint(
            "(storage_key IS NULL AND original_filename IS NULL AND media_type IS NULL AND size_bytes IS NULL AND sha256 IS NULL) "
            "OR (storage_key IS NOT NULL AND original_filename IS NOT NULL AND media_type IS NOT NULL AND size_bytes IS NOT NULL AND sha256 IS NOT NULL)",
            name="ck_course_materials_storage_metadata",
        ),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes > 0", name="ck_course_materials_size"),
        sa.CheckConstraint("sha256 IS NULL OR length(sha256) = 64", name="ck_course_materials_sha256"),
    )
    op.create_index("ix_course_materials_chapter_id", "course_materials", ["chapter_id"])
    op.create_index("ix_course_materials_lesson_id", "course_materials", ["lesson_id"])
    op.create_index("ix_course_materials_created_by_id", "course_materials", ["created_by_id"])
    op.create_index("ix_course_materials_status", "course_materials", ["status"])
    op.create_index(
        "uq_course_materials_chapter_position", "course_materials", ["chapter_id", "position"], unique=True,
        postgresql_where=sa.text("chapter_id IS NOT NULL"),
    )
    op.create_index(
        "uq_course_materials_lesson_position", "course_materials", ["lesson_id", "position"], unique=True,
        postgresql_where=sa.text("lesson_id IS NOT NULL"),
    )


def downgrade():
    op.drop_index("uq_course_materials_lesson_position", table_name="course_materials")
    op.drop_index("uq_course_materials_chapter_position", table_name="course_materials")
    op.drop_index("ix_course_materials_status", table_name="course_materials")
    op.drop_index("ix_course_materials_created_by_id", table_name="course_materials")
    op.drop_index("ix_course_materials_lesson_id", table_name="course_materials")
    op.drop_index("ix_course_materials_chapter_id", table_name="course_materials")
    op.drop_table("course_materials")

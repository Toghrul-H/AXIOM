"""Add authenticated course announcements.

Revision ID: 0030
Revises: 0029
"""
from alembic import op
import sqlalchemy as sa
revision="0030"
down_revision="0029"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("course_announcements", sa.Column("id",sa.Integer(),primary_key=True), sa.Column("title",sa.String(200),nullable=False), sa.Column("body",sa.Text(),nullable=False), sa.Column("category",sa.String(12),nullable=False,server_default="GENERAL"), sa.Column("link",sa.String(240)), sa.Column("pinned",sa.Boolean(),nullable=False,server_default=sa.text("false")), sa.Column("status",sa.String(12),nullable=False,server_default="draft"), sa.Column("created_by_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False), sa.Column("published_at",sa.DateTime(timezone=True)), sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()), sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()), sa.CheckConstraint("category IN ('IMPORTANT', 'GENERAL')",name="ck_course_announcements_category"),sa.CheckConstraint("status IN ('draft', 'published')",name="ck_course_announcements_status"),sa.CheckConstraint("link IS NULL OR (link LIKE '/%' AND link NOT LIKE '//%')",name="ck_course_announcements_link"))
    op.create_index("ix_course_announcements_status","course_announcements",["status"]); op.create_index("ix_course_announcements_published_at","course_announcements",["published_at"])
    op.create_table("course_announcement_reads",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("announcement_id",sa.Integer(),sa.ForeignKey("course_announcements.id",ondelete="CASCADE"),nullable=False),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("read_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint("announcement_id","user_id",name="uq_course_announcement_reads_user"))
    op.create_index("ix_course_announcement_reads_announcement_id","course_announcement_reads",["announcement_id"]); op.create_index("ix_course_announcement_reads_user_id","course_announcement_reads",["user_id"])
def downgrade():
    op.drop_index("ix_course_announcement_reads_user_id",table_name="course_announcement_reads");op.drop_index("ix_course_announcement_reads_announcement_id",table_name="course_announcement_reads");op.drop_table("course_announcement_reads");op.drop_index("ix_course_announcements_published_at",table_name="course_announcements");op.drop_index("ix_course_announcements_status",table_name="course_announcements");op.drop_table("course_announcements")

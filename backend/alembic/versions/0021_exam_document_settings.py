"""Persist safe Exam Builder document settings.

Revision ID: 0021
Revises: 0020
"""
from alembic import op
import sqlalchemy as sa


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


_DEFAULT_SETTINGS = """'{"header":{"institution_name":"Eötvös Loránd University","course_name":"Discrete Mathematics I","instructor_name":null,"document_date":null,"duration_minutes":null},"layout":{"paper_size":"A4","margins":"normal","question_spacing":"normal","page_numbering":true},"student_fields":{"show_name":true,"show_neptun_code":true,"show_date":true},"questions":{"show_points":true,"answer_space":"medium","numbering_enabled":true,"page_break_before_question_ids":[]}}'"""


def upgrade():
    op.add_column(
        "exams",
        sa.Column("document_settings", sa.JSON(), nullable=False, server_default=sa.text(_DEFAULT_SETTINGS)),
    )


def downgrade():
    op.drop_column("exams", "document_settings")

"""Persist safe practice-sheet document settings.

Revision ID: 0020
Revises: 0019
"""
from alembic import op
import sqlalchemy as sa


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

# Use a SQLAlchemy literal rather than ``sa.text`` below. ``text()`` parses
# JSON's ``:null``/``:true`` tokens as bind parameters on PostgreSQL.
_DEFAULT_SETTINGS = '{"header":{"institution_name":"Eötvös Loránd University","course_name":"Discrete Mathematics I","instructor_name":null,"document_date":null,"logo_visible":true},"layout":{"paper_size":"A4","margins":"normal","question_spacing":"normal"},"questions":{"show_points":true,"answer_space":"medium","numbering_enabled":true,"page_break_before_question_ids":[]}}'


def upgrade():
    op.add_column(
        "practice_sheets",
        sa.Column("document_settings", sa.JSON(), nullable=False, server_default=sa.literal(_DEFAULT_SETTINGS, type_=sa.String())),
    )


def downgrade():
    op.drop_column("practice_sheets", "document_settings")

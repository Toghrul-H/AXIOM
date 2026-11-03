"""Store stable external IDs and source references for curated imports.

Revision ID: 0013
Revises: 0012
"""
from alembic import op
import sqlalchemy as sa


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable fields preserve every existing Question unchanged. PostgreSQL
    # permits multiple NULL values under a unique constraint.
    op.add_column("questions", sa.Column("external_source_id", sa.String(length=80), nullable=True))
    op.add_column("questions", sa.Column("source_reference", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_questions_external_source_id", "questions", ["external_source_id"])


def downgrade():
    op.drop_constraint("uq_questions_external_source_id", "questions", type_="unique")
    op.drop_column("questions", "source_reference")
    op.drop_column("questions", "external_source_id")

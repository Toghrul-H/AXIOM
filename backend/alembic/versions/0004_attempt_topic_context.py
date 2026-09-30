"""Preserve topic context for mathematical input on new attempt snapshots.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    # Historical topics are unknown; old attempts retain NULL and use a general toolbar.
    op.add_column('attempt_answers', sa.Column('topic_slug',sa.String(120),nullable=True))


def downgrade():
    op.drop_column('attempt_answers','topic_slug')

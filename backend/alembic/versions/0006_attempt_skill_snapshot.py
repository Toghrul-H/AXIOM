"""Preserve skill attribution for new attempts; historical skills remain unknown."""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('attempt_answers', sa.Column('skill_code', sa.String(40), nullable=True))


def downgrade():
    op.drop_column('attempt_answers', 'skill_code')

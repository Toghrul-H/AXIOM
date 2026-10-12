"""Separate scheduled and writing intervals; latest arrival already exists in 0010."""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('assessment_events', sa.Column('writing_start_time', sa.Time(), nullable=True))
    op.add_column('assessment_events', sa.Column('writing_end_time', sa.Time(), nullable=True))
    op.create_check_constraint('ck_assessment_writing_times', 'assessment_events',
        'writing_end_time IS NULL OR writing_start_time IS NULL OR writing_end_time > writing_start_time')

def downgrade():
    op.drop_constraint('ck_assessment_writing_times', 'assessment_events', type_='check')
    op.drop_column('assessment_events', 'writing_end_time')
    op.drop_column('assessment_events', 'writing_start_time')

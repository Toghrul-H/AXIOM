"""Manual grades on immutable attempt answers. Existing answers remain ungraded."""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('attempt_answers', sa.Column('manual_points', sa.Integer(), nullable=True))
    op.add_column('attempt_answers', sa.Column('manual_feedback', sa.Text(), nullable=True))
    op.add_column('attempt_answers', sa.Column('graded_by_id', sa.Integer(), nullable=True))
    op.add_column('attempt_answers', sa.Column('graded_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key('fk_attempt_answers_graded_by', 'attempt_answers', 'users', ['graded_by_id'], ['id'], ondelete='RESTRICT')
    op.create_index('ix_attempt_answers_graded_by_id', 'attempt_answers', ['graded_by_id'])
    op.create_check_constraint('ck_attempt_answers_manual_grade', 'attempt_answers', "(manual_points IS NULL AND manual_feedback IS NULL AND graded_by_id IS NULL AND graded_at IS NULL) OR (response_type = 'FREE_RESPONSE' AND manual_points IS NOT NULL AND manual_points >= 0 AND manual_points <= points AND graded_by_id IS NOT NULL AND graded_at IS NOT NULL)")


def downgrade():
    op.drop_constraint('ck_attempt_answers_manual_grade', 'attempt_answers', type_='check')
    op.drop_index('ix_attempt_answers_graded_by_id', table_name='attempt_answers')
    op.drop_constraint('fk_attempt_answers_graded_by', 'attempt_answers', type_='foreignkey')
    for name in ['graded_at', 'graded_by_id', 'manual_feedback', 'manual_points']:
        op.drop_column('attempt_answers', name)

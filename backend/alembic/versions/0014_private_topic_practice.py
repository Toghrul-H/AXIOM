"""Keep dynamically composed student practice sessions private.

Revision ID: 0014
Revises: 0013
"""
from alembic import op
import sqlalchemy as sa


revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('quizzes', sa.Column('is_practice', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('quizzes', sa.Column('practice_owner_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_quizzes_practice_owner', 'quizzes', 'users', ['practice_owner_id'], ['id'], ondelete='RESTRICT')
    op.create_index('ix_quizzes_is_practice', 'quizzes', ['is_practice'])
    op.create_index('ix_quizzes_practice_owner_id', 'quizzes', ['practice_owner_id'])
    op.create_check_constraint(
        'ck_quizzes_practice_owner', 'quizzes',
        '(is_practice = false AND practice_owner_id IS NULL) OR (is_practice = true AND practice_owner_id IS NOT NULL)',
    )


def downgrade():
    op.drop_constraint('ck_quizzes_practice_owner', 'quizzes', type_='check')
    op.drop_index('ix_quizzes_practice_owner_id', table_name='quizzes')
    op.drop_index('ix_quizzes_is_practice', table_name='quizzes')
    op.drop_constraint('fk_quizzes_practice_owner', 'quizzes', type_='foreignkey')
    op.drop_column('quizzes', 'practice_owner_id')
    op.drop_column('quizzes', 'is_practice')

"""Accounts, revocable sessions, and preserved legacy attempt ownership.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('email',sa.String(254),nullable=False,unique=True),
        sa.Column('password_hash',sa.String(512),nullable=True),
        sa.Column('role',sa.String(20),nullable=False,server_default='STUDENT'),
        sa.Column('is_active',sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column('is_legacy',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('STUDENT','DEMONSTRATOR','LECTURER','ADMIN')",name='ck_users_role'))
    op.create_table('auth_sessions',
        sa.Column('token_hash',sa.String(64),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('csrf_token',sa.String(64),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_auth_sessions_user_id','auth_sessions',['user_id'])
    op.create_index('ix_auth_sessions_expires_at','auth_sessions',['expires_at'])
    op.add_column('quiz_attempts',sa.Column('user_id',sa.Integer(),nullable=True))
    op.execute("INSERT INTO users(email,role,is_active,is_legacy) VALUES ('legacy-attempts@migration.invalid','STUDENT',false,true)")
    op.execute("UPDATE quiz_attempts SET user_id=(SELECT id FROM users WHERE is_legacy=true)")
    op.alter_column('quiz_attempts','user_id',nullable=False)
    op.create_foreign_key('fk_quiz_attempts_user_id','quiz_attempts','users',['user_id'],['id'],ondelete='RESTRICT')
    op.create_index('ix_quiz_attempts_user_id','quiz_attempts',['user_id'])
    # Kept solely as historical audit data. It is never accepted as authentication.
    op.alter_column('quiz_attempts','development_session_id',nullable=True)


def downgrade():
    # New accounts/attempts cannot safely return to development-only identity.
    raise RuntimeError('0005 is forward-only: restore an explicit pre-migration backup to roll back authentication')

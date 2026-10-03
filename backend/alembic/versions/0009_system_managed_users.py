"""Protected accounts default off for all existing users."""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('is_system_managed', sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column('users', 'is_system_managed')

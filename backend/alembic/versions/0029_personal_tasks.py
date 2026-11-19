"""Add private student dashboard tasks.

Revision ID: 0029
Revises: 0028
"""

from alembic import op
import sqlalchemy as sa


revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "personal_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_personal_tasks_title"),
        sa.CheckConstraint(
            "(completed = false AND completed_at IS NULL) OR "
            "(completed = true AND completed_at IS NOT NULL)",
            name="ck_personal_tasks_completion",
        ),
    )
    op.create_index("ix_personal_tasks_user_id", "personal_tasks", ["user_id"])
    op.create_index("ix_personal_tasks_due_date", "personal_tasks", ["due_date"])
    op.create_index("ix_personal_tasks_completed", "personal_tasks", ["completed"])
    op.create_index(
        "ix_personal_tasks_user_completed_due",
        "personal_tasks",
        ["user_id", "completed", "due_date", "id"],
    )


def downgrade():
    op.drop_index("ix_personal_tasks_user_completed_due", table_name="personal_tasks")
    op.drop_index("ix_personal_tasks_completed", table_name="personal_tasks")
    op.drop_index("ix_personal_tasks_due_date", table_name="personal_tasks")
    op.drop_index("ix_personal_tasks_user_id", table_name="personal_tasks")
    op.drop_table("personal_tasks")

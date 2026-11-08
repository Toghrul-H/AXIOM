"""Add decision audit fields for demonstrator application review.

Revision ID: 0016
Revises: 0015
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("demonstrator_applications", sa.Column("decision_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("demonstrator_applications", sa.Column("decision_by_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_demonstrator_applications_decision_by_id",
        "demonstrator_applications",
        "users",
        ["decision_by_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_demonstrator_applications_decision_by_id", "demonstrator_applications", ["decision_by_id"])


def downgrade():
    op.drop_index("ix_demonstrator_applications_decision_by_id", table_name="demonstrator_applications")
    op.drop_constraint("fk_demonstrator_applications_decision_by_id", "demonstrator_applications", type_="foreignkey")
    op.drop_column("demonstrator_applications", "decision_by_id")
    op.drop_column("demonstrator_applications", "decision_at")

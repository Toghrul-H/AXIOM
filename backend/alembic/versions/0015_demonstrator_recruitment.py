"""Add private demonstrator recruitment data.

Revision ID: 0015
Revises: 0014
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("demonstrator_vacancies", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("course_name", sa.String(200), nullable=False), sa.Column("semester", sa.String(80), nullable=False), sa.Column("available_positions", sa.Integer(), nullable=False), sa.Column("description", sa.Text(), nullable=False), sa.Column("responsibilities", sa.Text(), nullable=False), sa.Column("opens_at", sa.DateTime(timezone=True)), sa.Column("closes_at", sa.DateTime(timezone=True)), sa.Column("state", sa.String(10), nullable=False, server_default="DRAFT"), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("published_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.CheckConstraint("state IN ('DRAFT','OPEN','CLOSED')", name="ck_demonstrator_vacancies_state"), sa.CheckConstraint("available_positions >= 0", name="ck_demonstrator_vacancies_positions"))
    op.create_index("ix_demonstrator_vacancies_state", "demonstrator_vacancies", ["state"]); op.create_index("ix_demonstrator_vacancies_closes_at", "demonstrator_vacancies", ["closes_at"]); op.create_index("ix_demonstrator_vacancies_created_by_id", "demonstrator_vacancies", ["created_by_id"])
    op.create_table("demonstrator_applications", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("demonstrator_vacancies.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("full_name", sa.String(200), nullable=False), sa.Column("neptun_code", sa.String(20), nullable=False), sa.Column("final_grade", sa.String(20)), sa.Column("practice_teacher", sa.String(200), nullable=False), sa.Column("completion_semester", sa.String(80), nullable=False), sa.Column("motivation", sa.Text(), nullable=False), sa.Column("teaching_experience", sa.Text(), nullable=False), sa.Column("responsibility_interest", sa.Text(), nullable=False), sa.Column("additional_information", sa.Text()), sa.Column("status", sa.String(20), nullable=False, server_default="SUBMITTED"), sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("vacancy_id", "user_id", name="uq_demonstrator_application_user"))
    op.create_index("ix_demonstrator_applications_vacancy_id", "demonstrator_applications", ["vacancy_id"]); op.create_index("ix_demonstrator_applications_user_id", "demonstrator_applications", ["user_id"]); op.create_index("ix_demonstrator_applications_status", "demonstrator_applications", ["status"]); op.create_index("ix_demonstrator_applications_submitted_at", "demonstrator_applications", ["submitted_at"])
    op.create_table("recruitment_notifications", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("demonstrator_vacancies.id", ondelete="CASCADE"), nullable=False), sa.Column("kind", sa.String(40), nullable=False, server_default="VACANCY_OPEN"), sa.Column("title", sa.String(160), nullable=False), sa.Column("body", sa.Text(), nullable=False), sa.Column("link", sa.String(240), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("user_id", "vacancy_id", "kind", name="uq_recruitment_notification"))
    op.create_index("ix_recruitment_notifications_user_id", "recruitment_notifications", ["user_id"]); op.create_index("ix_recruitment_notifications_vacancy_id", "recruitment_notifications", ["vacancy_id"])


def downgrade():
    op.drop_table("recruitment_notifications"); op.drop_table("demonstrator_applications"); op.drop_table("demonstrator_vacancies")

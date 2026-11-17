"""Add opt-in, private Study Partner profiles and requests.

Revision ID: 0022
Revises: 0021
"""

from alembic import op
import sqlalchemy as sa


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "study_partner_profiles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("display_name", sa.String(length=60), nullable=False),
        sa.Column("is_participating", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_discoverable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("study_format", sa.String(length=12), nullable=False, server_default="EITHER"),
        sa.Column("introduction", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("study_format IN ('ONLINE', 'IN_PERSON', 'EITHER')", name="ck_study_partner_profiles_format"),
        sa.CheckConstraint("NOT is_discoverable OR is_participating", name="ck_study_partner_profiles_discoverable"),
    )
    op.create_index("ix_study_partner_profiles_is_participating", "study_partner_profiles", ["is_participating"])
    op.create_index("ix_study_partner_profiles_is_discoverable", "study_partner_profiles", ["is_discoverable"])
    op.create_index("ix_study_partner_profiles_discovery", "study_partner_profiles", ["is_participating", "is_discoverable", "study_format"])
    op.create_table(
        "study_partner_topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_user_id", sa.Integer(), sa.ForeignKey("study_partner_profiles.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.UniqueConstraint("profile_user_id", "topic_id", "purpose", name="uq_study_partner_topics_preference"),
        sa.CheckConstraint("purpose IN ('WANT_TO_STUDY', 'CAN_HELP')", name="ck_study_partner_topics_purpose"),
    )
    op.create_index("ix_study_partner_topics_profile_user_id", "study_partner_topics", ["profile_user_id"])
    op.create_index("ix_study_partner_topics_topic_id", "study_partner_topics", ["topic_id"])
    op.create_index("ix_study_partner_topics_topic_purpose", "study_partner_topics", ["topic_id", "purpose"])
    op.create_table(
        "study_partner_availability",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_user_id", sa.Integer(), sa.ForeignKey("study_partner_profiles.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.Column("end_minute", sa.Integer(), nullable=False),
        sa.UniqueConstraint("profile_user_id", "weekday", "start_minute", "end_minute", name="uq_study_partner_availability_slot"),
        sa.CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_study_partner_availability_weekday"),
        sa.CheckConstraint("start_minute >= 0 AND start_minute < end_minute AND end_minute <= 1440", name="ck_study_partner_availability_range"),
    )
    op.create_index("ix_study_partner_availability_profile_user_id", "study_partner_availability", ["profile_user_id"])
    op.create_index("ix_study_partner_availability_profile_weekday", "study_partner_availability", ["profile_user_id", "weekday"])
    op.create_table(
        "study_partner_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("requester_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pair_low_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pair_high_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("requester_user_id <> recipient_user_id", name="ck_study_partner_requests_not_self"),
        sa.CheckConstraint("pair_low_user_id < pair_high_user_id", name="ck_study_partner_requests_pair_order"),
        sa.CheckConstraint("(requester_user_id = pair_low_user_id AND recipient_user_id = pair_high_user_id) OR (requester_user_id = pair_high_user_id AND recipient_user_id = pair_low_user_id)", name="ck_study_partner_requests_pair_members"),
        sa.CheckConstraint("status IN ('PENDING', 'ACCEPTED', 'DECLINED', 'CANCELLED')", name="ck_study_partner_requests_status"),
    )
    op.create_index("ix_study_partner_requests_requester_user_id", "study_partner_requests", ["requester_user_id"])
    op.create_index("ix_study_partner_requests_recipient_user_id", "study_partner_requests", ["recipient_user_id"])
    op.create_index("ix_study_partner_requests_status", "study_partner_requests", ["status"])
    op.create_index("ix_study_partner_requests_requester_status", "study_partner_requests", ["requester_user_id", "status"])
    op.create_index("ix_study_partner_requests_recipient_status", "study_partner_requests", ["recipient_user_id", "status"])
    op.create_index("uq_study_partner_requests_pending_pair", "study_partner_requests", ["pair_low_user_id", "pair_high_user_id"], unique=True, postgresql_where=sa.text("status = 'PENDING'"))
    op.create_table(
        "study_partner_blocks",
        sa.Column("blocker_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("blocked_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("blocker_user_id <> blocked_user_id", name="ck_study_partner_blocks_not_self"),
    )
    op.create_index("ix_study_partner_blocks_blocked", "study_partner_blocks", ["blocked_user_id"])


def downgrade():
    op.drop_index("ix_study_partner_blocks_blocked", table_name="study_partner_blocks")
    op.drop_table("study_partner_blocks")
    op.drop_index("uq_study_partner_requests_pending_pair", table_name="study_partner_requests")
    op.drop_index("ix_study_partner_requests_recipient_status", table_name="study_partner_requests")
    op.drop_index("ix_study_partner_requests_requester_status", table_name="study_partner_requests")
    op.drop_index("ix_study_partner_requests_status", table_name="study_partner_requests")
    op.drop_index("ix_study_partner_requests_recipient_user_id", table_name="study_partner_requests")
    op.drop_index("ix_study_partner_requests_requester_user_id", table_name="study_partner_requests")
    op.drop_table("study_partner_requests")
    op.drop_index("ix_study_partner_availability_profile_weekday", table_name="study_partner_availability")
    op.drop_index("ix_study_partner_availability_profile_user_id", table_name="study_partner_availability")
    op.drop_table("study_partner_availability")
    op.drop_index("ix_study_partner_topics_topic_purpose", table_name="study_partner_topics")
    op.drop_index("ix_study_partner_topics_topic_id", table_name="study_partner_topics")
    op.drop_index("ix_study_partner_topics_profile_user_id", table_name="study_partner_topics")
    op.drop_table("study_partner_topics")
    op.drop_index("ix_study_partner_profiles_discovery", table_name="study_partner_profiles")
    op.drop_index("ix_study_partner_profiles_is_discoverable", table_name="study_partner_profiles")
    op.drop_index("ix_study_partner_profiles_is_participating", table_name="study_partner_profiles")
    op.drop_table("study_partner_profiles")

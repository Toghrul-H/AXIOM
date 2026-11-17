"""Private, opt-in Study Partner records."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StudyPartnerProfile(Base):
    __tablename__ = "study_partner_profiles"
    __table_args__ = (
        CheckConstraint("study_format IN ('ONLINE', 'IN_PERSON', 'EITHER')", name="ck_study_partner_profiles_format"),
        CheckConstraint("NOT is_discoverable OR is_participating", name="ck_study_partner_profiles_discoverable"),
        Index("ix_study_partner_profiles_discovery", "is_participating", "is_discoverable", "study_format"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(60))
    is_participating: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    is_discoverable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", index=True)
    study_format: Mapped[str] = mapped_column(String(12), default="EITHER", server_default="EITHER")
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StudyPartnerTopic(Base):
    __tablename__ = "study_partner_topics"
    __table_args__ = (
        UniqueConstraint("profile_user_id", "topic_id", "purpose", name="uq_study_partner_topics_preference"),
        CheckConstraint("purpose IN ('WANT_TO_STUDY', 'CAN_HELP')", name="ck_study_partner_topics_purpose"),
        Index("ix_study_partner_topics_topic_purpose", "topic_id", "purpose"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_user_id: Mapped[int] = mapped_column(ForeignKey("study_partner_profiles.user_id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="RESTRICT"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))


class StudyPartnerAvailability(Base):
    __tablename__ = "study_partner_availability"
    __table_args__ = (
        UniqueConstraint("profile_user_id", "weekday", "start_minute", "end_minute", name="uq_study_partner_availability_slot"),
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_study_partner_availability_weekday"),
        CheckConstraint("start_minute >= 0 AND start_minute < end_minute AND end_minute <= 1440", name="ck_study_partner_availability_range"),
        Index("ix_study_partner_availability_profile_weekday", "profile_user_id", "weekday"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_user_id: Mapped[int] = mapped_column(ForeignKey("study_partner_profiles.user_id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    start_minute: Mapped[int] = mapped_column(Integer)
    end_minute: Mapped[int] = mapped_column(Integer)


class StudyPartnerRequest(Base):
    __tablename__ = "study_partner_requests"
    __table_args__ = (
        CheckConstraint("requester_user_id <> recipient_user_id", name="ck_study_partner_requests_not_self"),
        CheckConstraint("pair_low_user_id < pair_high_user_id", name="ck_study_partner_requests_pair_order"),
        CheckConstraint(
            "(requester_user_id = pair_low_user_id AND recipient_user_id = pair_high_user_id) OR "
            "(requester_user_id = pair_high_user_id AND recipient_user_id = pair_low_user_id)",
            name="ck_study_partner_requests_pair_members",
        ),
        CheckConstraint("status IN ('PENDING', 'ACCEPTED', 'DECLINED', 'CANCELLED')", name="ck_study_partner_requests_status"),
        Index("ix_study_partner_requests_requester_status", "requester_user_id", "status"),
        Index("ix_study_partner_requests_recipient_status", "recipient_user_id", "status"),
        Index(
            "uq_study_partner_requests_pending_pair",
            "pair_low_user_id",
            "pair_high_user_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
            sqlite_where=text("status = 'PENDING'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    pair_low_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    pair_high_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(12), default="PENDING", server_default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StudyPartnerBlock(Base):
    __tablename__ = "study_partner_blocks"
    __table_args__ = (
        CheckConstraint("blocker_user_id <> blocked_user_id", name="ck_study_partner_blocks_not_self"),
        Index("ix_study_partner_blocks_blocked", "blocked_user_id"),
    )

    blocker_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    blocked_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

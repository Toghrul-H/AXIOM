"""Private, opt-in Study Partner records."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
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


class StudyPartnerMessage(Base):
    __tablename__ = "study_partner_messages"
    __table_args__ = (
        CheckConstraint("length(content) <= 2000", name="ck_study_partner_messages_content_length"),
        Index("ix_study_partner_messages_request_created", "request_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("study_partner_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reply_to_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_partner_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StudyPartnerMessageReaction(Base):
    __tablename__ = "study_partner_message_reactions"
    __table_args__ = (
        CheckConstraint("emoji IN ('👍', '❤️', '😂', '😮', '😢', '🎉')", name="ck_study_partner_message_reactions_emoji"),
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_study_partner_message_reactions_user_emoji"),
        Index("ix_study_partner_message_reactions_message", "message_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("study_partner_messages.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    emoji: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StudyPartnerChatReceipt(Base):
    __tablename__ = "study_partner_chat_receipts"
    __table_args__ = (
        Index("ix_study_partner_chat_receipts_user", "user_id"),
        Index("ix_study_partner_chat_receipts_typing_expires", "typing_expires_at"),
    )

    request_id: Mapped[int] = mapped_column(
        ForeignKey("study_partner_requests.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    last_read_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_partner_messages.id", ondelete="SET NULL"), nullable=True
    )
    typing_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class StudyPartnerMessageAttachment(Base):
    __tablename__ = "study_partner_message_attachments"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_study_partner_message_attachments_size"),
        CheckConstraint("length(sha256) = 64", name="ck_study_partner_message_attachments_sha256"),
        Index("ix_study_partner_message_attachments_request", "request_id"),
        Index("ix_study_partner_message_attachments_message", "message_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("study_partner_requests.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_partner_messages.id", ondelete="SET NULL"), nullable=True
    )
    uploader_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(180), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

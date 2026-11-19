from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CourseAnnouncement(Base):
    __tablename__ = "course_announcements"
    __table_args__ = (
        CheckConstraint("category IN ('IMPORTANT', 'GENERAL')", name="ck_course_announcements_category"),
        CheckConstraint("status IN ('draft', 'published')", name="ck_course_announcements_status"),
        CheckConstraint("link IS NULL OR (link LIKE '/%' AND link NOT LIKE '//%')", name="ck_course_announcements_link"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(12), default="GENERAL", server_default="GENERAL", index=True)
    link: Mapped[str | None] = mapped_column(String(240), nullable=True)
    pinned: Mapped[bool] = mapped_column(default=False, server_default="false", index=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", server_default="draft", index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CourseAnnouncementRead(Base):
    __tablename__ = "course_announcement_reads"
    __table_args__ = (UniqueConstraint("announcement_id", "user_id", name="uq_course_announcement_reads_user"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    announcement_id: Mapped[int] = mapped_column(ForeignKey("course_announcements.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

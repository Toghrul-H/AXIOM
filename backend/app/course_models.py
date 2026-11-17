"""Staff-authored course chapters, lessons, and question references."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CourseChapter(Base):
    __tablename__ = "course_chapters"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_course_chapters_slug"),
        UniqueConstraint("position", name="uq_course_chapters_position"),
        CheckConstraint("position >= 0", name="ck_course_chapters_position"),
        CheckConstraint("status IN ('draft', 'published')", name="ck_course_chapters_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120))
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="draft", server_default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    lessons: Mapped[list["CourseLesson"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin", order_by="CourseLesson.position"
    )


class CourseLesson(Base):
    __tablename__ = "course_lessons"
    __table_args__ = (
        UniqueConstraint("chapter_id", "slug", name="uq_course_lessons_chapter_slug"),
        UniqueConstraint("chapter_id", "position", name="uq_course_lessons_chapter_position"),
        CheckConstraint("position >= 0", name="ck_course_lessons_position"),
        CheckConstraint("status IN ('draft', 'published')", name="ck_course_lessons_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("course_chapters.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120))
    # Stored as explanatory source text. It is rendered only by the existing safe client-side math renderer.
    content: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="draft", server_default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    questions: Mapped[list["CourseLessonQuestion"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin", order_by="CourseLessonQuestion.position"
    )


class CourseLessonQuestion(Base):
    __tablename__ = "course_lesson_questions"
    __table_args__ = (
        UniqueConstraint("lesson_id", "question_id", name="uq_course_lesson_questions_question"),
        UniqueConstraint("lesson_id", "position", name="uq_course_lesson_questions_position"),
        CheckConstraint("position >= 0", name="ck_course_lesson_questions_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("course_lessons.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), index=True)
    position: Mapped[int] = mapped_column(Integer)

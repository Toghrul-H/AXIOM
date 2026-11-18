"""Staff-authored course chapters, lessons, and question references."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
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
    materials: Mapped[list["CourseMaterial"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin", order_by="CourseMaterial.position"
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
    materials: Mapped[list["CourseMaterial"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin", order_by="CourseMaterial.position"
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


class CourseMaterial(Base):
    """Metadata for a private object-store file attached to one course container."""

    __tablename__ = "course_materials"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_course_materials_position"),
        CheckConstraint("status IN ('draft', 'published')", name="ck_course_materials_status"),
        CheckConstraint(
            "(chapter_id IS NOT NULL AND lesson_id IS NULL) OR "
            "(chapter_id IS NULL AND lesson_id IS NOT NULL)",
            name="ck_course_materials_exactly_one_parent",
        ),
        CheckConstraint(
            "(storage_key IS NULL AND original_filename IS NULL AND media_type IS NULL "
            "AND size_bytes IS NULL AND sha256 IS NULL) OR "
            "(storage_key IS NOT NULL AND original_filename IS NOT NULL AND media_type IS NOT NULL "
            "AND size_bytes IS NOT NULL AND sha256 IS NOT NULL)",
            name="ck_course_materials_storage_metadata",
        ),
        CheckConstraint("size_bytes IS NULL OR size_bytes > 0", name="ck_course_materials_size"),
        CheckConstraint("sha256 IS NULL OR length(sha256) = 64", name="ck_course_materials_sha256"),
        Index(
            "uq_course_materials_chapter_position",
            "chapter_id",
            "position",
            unique=True,
            postgresql_where=text("chapter_id IS NOT NULL"),
            sqlite_where=text("chapter_id IS NOT NULL"),
        ),
        Index(
            "uq_course_materials_lesson_position",
            "lesson_id",
            "position",
            unique=True,
            postgresql_where=text("lesson_id IS NOT NULL"),
            sqlite_where=text("lesson_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_chapters.id", ondelete="CASCADE"), nullable=True, index=True
    )
    lesson_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True, unique=True)
    media_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", server_default="draft", index=True)
    position: Mapped[int] = mapped_column(Integer)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

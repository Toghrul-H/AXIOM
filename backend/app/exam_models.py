"""Staff-authored printable exam compositions and immutable final snapshots."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Exam(Base):
    __tablename__ = "exams"
    __table_args__ = (
        CheckConstraint("status IN ('draft','finalized')", name="ck_exams_status"),
        CheckConstraint(
            "(status = 'draft' AND finalized_at IS NULL AND question_snapshot IS NULL) OR "
            "(status = 'finalized' AND finalized_at IS NOT NULL AND question_snapshot IS NOT NULL)",
            name="ck_exams_finalization_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", server_default="draft", index=True)
    assessment_configuration_id: Mapped[int | None] = mapped_column(
        ForeignKey("assessment_configurations.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Kept private to staff-only services; contains answer material for the key.
    question_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    questions: Mapped[list["ExamQuestion"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="ExamQuestion.position",
    )


class ExamQuestion(Base):
    __tablename__ = "exam_questions"
    __table_args__ = (
        UniqueConstraint("exam_id", "question_id", name="uq_exam_questions_question"),
        UniqueConstraint("exam_id", "position", name="uq_exam_questions_position"),
        CheckConstraint("position >= 0", name="ck_exam_questions_position"),
        CheckConstraint("points > 0 AND points <= 1000", name="ck_exam_questions_points"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    points: Mapped[int] = mapped_column(Integer)

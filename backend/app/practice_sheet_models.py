"""Staff-authored practice-sheet compositions and immutable question-set variants."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.practice_sheet_settings import default_document_settings


class PracticeSheet(Base):
    __tablename__ = "practice_sheets"
    __table_args__ = (
        CheckConstraint("status IN ('draft','finalized')", name="ck_practice_sheets_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="draft", server_default="draft", index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    document_settings: Mapped[dict] = mapped_column(
        JSON,
        default=default_document_settings,
        server_default=text("'{\"header\":{\"institution_name\":\"Eötvös Loránd University\",\"course_name\":\"Discrete Mathematics I\",\"instructor_name\":null,\"document_date\":null,\"logo_visible\":true},\"layout\":{\"paper_size\":\"A4\",\"margins\":\"normal\",\"question_spacing\":\"normal\"},\"questions\":{\"show_points\":true,\"answer_space\":\"medium\",\"numbering_enabled\":true,\"page_break_before_question_ids\":[]}}'"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    questions: Mapped[list["PracticeSheetQuestion"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin",
        order_by="PracticeSheetQuestion.position",
    )
    variants: Mapped[list["PracticeSheetVariant"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin",
        order_by="PracticeSheetVariant.label",
    )


class PracticeSheetQuestion(Base):
    __tablename__ = "practice_sheet_questions"
    __table_args__ = (
        UniqueConstraint("practice_sheet_id", "question_id", name="uq_practice_sheet_questions_question"),
        UniqueConstraint("practice_sheet_id", "position", name="uq_practice_sheet_questions_position"),
        CheckConstraint("position >= 0", name="ck_practice_sheet_questions_position"),
        CheckConstraint("points IS NULL OR (points > 0 AND points <= 1000)", name="ck_practice_sheet_questions_points"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    practice_sheet_id: Mapped[int] = mapped_column(ForeignKey("practice_sheets.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    points: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PracticeSheetVariant(Base):
    __tablename__ = "practice_sheet_variants"
    __table_args__ = (UniqueConstraint("practice_sheet_id", "label", name="uq_practice_sheet_variants_label"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    practice_sheet_id: Mapped[int] = mapped_column(ForeignKey("practice_sheets.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(16))
    question_snapshot: Mapped[dict] = mapped_column(JSON)
    seed: Mapped[str] = mapped_column(String(120))
    generator_version: Mapped[str] = mapped_column(String(40), default="question-set-v1", server_default="question-set-v1")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

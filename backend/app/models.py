from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

question_problem_sets = Table(
    "question_problem_sets", Base.metadata,
    Column("question_id", ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
    Column("problem_set_id", ForeignKey("problem_sets.id", ondelete="RESTRICT"), primary_key=True, index=True),
)
question_suitabilities = Table(
    "question_suitabilities", Base.metadata,
    Column("question_id", ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
    Column("suitability_code", ForeignKey("assessment_suitabilities.code", ondelete="RESTRICT"), primary_key=True, index=True),
)


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_topics_not_self"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="RESTRICT"), index=True)
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")
    parent: Mapped["Topic | None"] = relationship(remote_side="Topic.id", lazy="joined", join_depth=1)


class ResponseType(Base):
    __tablename__ = "response_types"
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")


class SkillType(Base):
    __tablename__ = "skill_types"
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")


class ProblemSet(Base):
    __tablename__ = "problem_sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")


class AssessmentSuitability(Base):
    __tablename__ = "assessment_suitabilities"
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="ck_questions_difficulty"),
        CheckConstraint(
            "(response_type = 'FREE_RESPONSE' AND expected_answer IS NOT NULL AND correct_boolean IS NULL) OR "
            "(response_type = 'TRUE_FALSE' AND expected_answer IS NULL AND correct_boolean IS NOT NULL) OR "
            "(response_type IN ('SINGLE_CHOICE', 'MULTIPLE_SELECT') AND expected_answer IS NULL AND correct_boolean IS NULL)",
            name="ck_questions_answer_storage",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str | None] = mapped_column(String(200))
    difficulty: Mapped[str] = mapped_column(String(10), index=True)
    response_type: Mapped[str] = mapped_column(ForeignKey("response_types.code", ondelete="RESTRICT"), index=True)
    skill_type: Mapped[str] = mapped_column(ForeignKey("skill_types.code", ondelete="RESTRICT"), index=True)
    question_text: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str | None] = mapped_column(Text)
    correct_boolean: Mapped[bool | None] = mapped_column(Boolean)
    explanation: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    topic: Mapped[Topic] = relationship(lazy="joined")
    options: Mapped[list["QuestionOption"]] = relationship(back_populates="question", cascade="all, delete-orphan", passive_deletes=True, order_by="QuestionOption.position", lazy="selectin")
    problem_sets: Mapped[list[ProblemSet]] = relationship(secondary=question_problem_sets, order_by="ProblemSet.sort_order", lazy="selectin", passive_deletes=True)
    assessment_suitabilities: Mapped[list[AssessmentSuitability]] = relationship(secondary=question_suitabilities, order_by="AssessmentSuitability.sort_order", lazy="selectin", passive_deletes=True)


class QuestionOption(Base):
    __tablename__ = "question_options"
    __table_args__ = (
        UniqueConstraint("question_id", "position", name="uq_question_options_position", deferrable=True, initially="DEFERRED"),
        CheckConstraint("position >= 0", name="ck_question_options_position"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    position: Mapped[int] = mapped_column(Integer)
    question: Mapped[Question] = relationship(back_populates="options")

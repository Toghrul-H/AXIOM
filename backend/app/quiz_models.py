"""Quiz composition and immutable per-attempt question snapshots."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Quiz(Base):
    __tablename__ = 'quizzes'
    __table_args__ = (CheckConstraint("status IN ('DRAFT','ACTIVE','INACTIVE')", name='ck_quizzes_status'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='DRAFT', server_default='DRAFT', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    questions: Mapped[list['QuizQuestion']] = relationship(cascade='all, delete-orphan', passive_deletes=True, lazy='selectin', order_by='QuizQuestion.position')


class QuizQuestion(Base):
    __tablename__ = 'quiz_questions'
    __table_args__ = (
        UniqueConstraint('quiz_id','position',name='uq_quiz_questions_position',deferrable=True,initially='DEFERRED'),
        CheckConstraint('position >= 0',name='ck_quiz_questions_position'),
        CheckConstraint('points > 0 AND points <= 1000',name='ck_quiz_questions_points'),
    )
    quiz_id: Mapped[int] = mapped_column(ForeignKey('quizzes.id',ondelete='CASCADE'),primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('questions.id',ondelete='CASCADE'),primary_key=True,index=True)
    position: Mapped[int]
    points: Mapped[int]


class QuizAttempt(Base):
    __tablename__ = 'quiz_attempts'
    __table_args__ = (
        CheckConstraint("status IN ('IN_PROGRESS','SUBMITTED')",name='ck_quiz_attempts_status'),
        CheckConstraint("(status = 'IN_PROGRESS' AND submitted_at IS NULL AND objective_score IS NULL) OR (status = 'SUBMITTED' AND submitted_at IS NOT NULL AND objective_score IS NOT NULL)",name='ck_quiz_attempts_submission'),
        CheckConstraint('objective_score IS NULL OR (objective_score >= 0 AND objective_score <= objective_total)',name='ck_quiz_attempts_score'),
    )
    id: Mapped[UUID] = mapped_column(Uuid,primary_key=True,default=uuid4)
    quiz_id: Mapped[int] = mapped_column(ForeignKey('quizzes.id',ondelete='RESTRICT'),index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='RESTRICT'),index=True)
    development_session_id: Mapped[UUID | None] = mapped_column(Uuid,index=True)
    quiz_title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20),default='IN_PROGRESS',server_default='IN_PROGRESS')
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    objective_score: Mapped[int | None]
    objective_total: Mapped[int]
    items: Mapped[list['AttemptAnswer']] = relationship(cascade='all, delete-orphan',passive_deletes=True,lazy='selectin',order_by='AttemptAnswer.position')


class AttemptAnswer(Base):
    """One relational question snapshot and saved answer per attempt question."""
    __tablename__ = 'attempt_answers'
    __table_args__ = (
        UniqueConstraint('quiz_attempt_id','position',name='uq_attempt_answers_position'),
        CheckConstraint('position >= 0 AND points > 0',name='ck_attempt_answers_position_points'),
        CheckConstraint('points_awarded IS NULL OR (points_awarded >= 0 AND points_awarded <= points)',name='ck_attempt_answers_awarded'),
        CheckConstraint("(manual_points IS NULL AND manual_feedback IS NULL AND graded_by_id IS NULL AND graded_at IS NULL) OR (response_type = 'FREE_RESPONSE' AND manual_points IS NOT NULL AND manual_points >= 0 AND manual_points <= points AND graded_by_id IS NOT NULL AND graded_at IS NOT NULL)", name='ck_attempt_answers_manual_grade'),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_attempt_id: Mapped[UUID] = mapped_column(ForeignKey('quiz_attempts.id',ondelete='CASCADE'),index=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey('questions.id',ondelete='SET NULL'),index=True)
    position: Mapped[int]
    points: Mapped[int]
    question_text: Mapped[str] = mapped_column(Text)
    topic_slug: Mapped[str | None] = mapped_column(String(120))
    skill_code: Mapped[str | None] = mapped_column(String(40))
    response_type: Mapped[str] = mapped_column(String(40))
    expected_answer: Mapped[str | None] = mapped_column(Text)
    correct_boolean: Mapped[bool | None] = mapped_column(Boolean)
    explanation: Mapped[str | None] = mapped_column(Text)
    # Only the variable-length selected snapshot-option IDs use JSON; not the attempt.
    selected_option_ids: Mapped[list[int]] = mapped_column(JSONB,default=list,server_default='[]')
    boolean_answer: Mapped[bool | None] = mapped_column(Boolean)
    free_response: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    points_awarded: Mapped[int | None]
    manual_points: Mapped[int | None]
    manual_feedback: Mapped[str | None] = mapped_column(Text)
    graded_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), index=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    options: Mapped[list['AttemptOption']] = relationship(cascade='all, delete-orphan',passive_deletes=True,lazy='selectin',order_by='AttemptOption.position')


class AttemptOption(Base):
    __tablename__ = 'attempt_options'
    __table_args__ = (UniqueConstraint('attempt_answer_id','position',name='uq_attempt_options_position'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_answer_id: Mapped[int] = mapped_column(ForeignKey('attempt_answers.id',ondelete='CASCADE'),index=True)
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    position: Mapped[int]

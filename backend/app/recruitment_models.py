"""Private demonstrator-recruitment records."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class DemonstratorVacancy(Base):
    __tablename__ = "demonstrator_vacancies"
    __table_args__ = (
        CheckConstraint("state IN ('DRAFT','OPEN','CLOSED')", name="ck_demonstrator_vacancies_state"),
        CheckConstraint("available_positions >= 0", name="ck_demonstrator_vacancies_positions"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    course_name: Mapped[str] = mapped_column(String(200))
    semester: Mapped[str] = mapped_column(String(80))
    available_positions: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    responsibilities: Mapped[str] = mapped_column(Text)
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(10), default="DRAFT", server_default="DRAFT", index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DemonstratorApplication(Base):
    __tablename__ = "demonstrator_applications"
    __table_args__ = (UniqueConstraint("vacancy_id", "user_id", name="uq_demonstrator_application_user"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("demonstrator_vacancies.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    neptun_code: Mapped[str] = mapped_column(String(20))
    final_grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    practice_teacher: Mapped[str] = mapped_column(String(200))
    completion_semester: Mapped[str] = mapped_column(String(80))
    motivation: Mapped[str] = mapped_column(Text)
    teaching_experience: Mapped[str] = mapped_column(Text)
    responsibility_interest: Mapped[str] = mapped_column(Text)
    additional_information: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="SUBMITTED", server_default="SUBMITTED", index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    # M13C fields stay nullable for applications submitted before the questionnaire existed.
    lecture_grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    practice_grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    weekly_availability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_responsibilities: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)


class DemonstratorQuestion(Base):
    """Lecturer-defined question for one vacancy; immutable after first application."""

    __tablename__ = "demonstrator_questions"
    __table_args__ = (UniqueConstraint("vacancy_id", "display_order", name="uq_demonstrator_question_order"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("demonstrator_vacancies.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(24))
    required: Mapped[bool] = mapped_column(default=False, server_default="false")
    options: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer)


class DemonstratorApplicationAnswer(Base):
    """Immutable custom-answer snapshot retaining the wording shown to a student."""

    __tablename__ = "demonstrator_application_answers"
    __table_args__ = (UniqueConstraint("application_id", "question_id", name="uq_demonstrator_application_answer"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("demonstrator_applications.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("demonstrator_questions.id", ondelete="RESTRICT"), index=True)
    question_title: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(24))
    answer: Mapped[object] = mapped_column(JSON)
    display_order: Mapped[int] = mapped_column(Integer)


class RecruitmentNotification(Base):
    __tablename__ = "recruitment_notifications"
    __table_args__ = (UniqueConstraint("user_id", "vacancy_id", "kind", name="uq_recruitment_notification"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("demonstrator_vacancies.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="VACANCY_OPEN", server_default="VACANCY_OPEN")
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

"""Private demonstrator-recruitment records."""
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
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

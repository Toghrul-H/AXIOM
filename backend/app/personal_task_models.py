"""Private, student-owned dashboard tasks."""

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PersonalTask(Base):
    __tablename__ = "personal_tasks"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_personal_tasks_title"),
        CheckConstraint(
            "(completed = false AND completed_at IS NULL) OR "
            "(completed = true AND completed_at IS NOT NULL)",
            name="ck_personal_tasks_completion",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    completed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

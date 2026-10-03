from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator
from app.schemas import Schema
from app.quiz_schemas import AttemptReview, ReviewItem


class ManualGradeWrite(Schema):
    points: int = Field(ge=0, le=1000, strict=True)
    feedback: str | None = Field(default=None, max_length=20000, strict=True)

    @field_validator('feedback')
    @classmethod
    def clean_feedback(cls, value):
        return value.strip() or None if value is not None else None


class GradingStudent(Schema):
    id: int
    email: str


class GradingQueueItem(Schema):
    attempt_id: UUID
    student: GradingStudent
    quiz_id: int
    quiz_title: str
    submitted_at: datetime
    manual_answer_count: int
    pending_count: int
    grading_status: Literal['PENDING', 'COMPLETED']


class GradingQueue(Schema):
    items: list[GradingQueueItem]
    total: int
    offset: int
    limit: int


class StaffReviewItem(ReviewItem):
    graded_by_id: int | None


class GradingAttempt(AttemptReview):
    student: GradingStudent
    items: list[StaffReviewItem]

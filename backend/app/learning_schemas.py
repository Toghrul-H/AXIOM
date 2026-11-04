"""Explicit student-learning and topic-practice API contracts."""
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas import NonBlank, Schema


class PracticeTopic(Schema):
    id: int
    slug: str
    name: str
    available_question_count: int = Field(ge=0)
    attempted_question_count: int = Field(ge=0)
    submitted_answer_count: int = Field(ge=0)
    pending_grading_count: int = Field(ge=0)
    graded_question_count: int = Field(ge=0)
    manual_points_awarded: int = Field(ge=0)
    manual_points_possible: int = Field(ge=0)
    graded_score_percent: float | None = Field(default=None, ge=0, le=100)


class PracticeStart(Schema):
    topic_slug: NonBlank
    question_count: int = Field(ge=1, le=20, strict=True)


class ContinueLearning(Schema):
    kind: Literal['RESUME_ATTEMPT', 'START_PRACTICE', 'BROWSE_PRACTICE']
    title: str
    description: str
    attempt_id: UUID | None = None
    topic_slug: str | None = None


class LearningOverview(Schema):
    total_attempted_questions: int = Field(ge=0)
    completed_practice_sessions: int = Field(ge=0)
    in_progress_sessions: int = Field(ge=0)
    pending_grading_count: int = Field(ge=0)
    graded_question_count: int = Field(ge=0)
    manual_points_awarded: int = Field(ge=0)
    manual_points_possible: int = Field(ge=0)
    graded_score_percent: float | None = Field(default=None, ge=0, le=100)


class LearningSummary(Schema):
    overview: LearningOverview
    topics: list[PracticeTopic]
    continue_learning: ContinueLearning

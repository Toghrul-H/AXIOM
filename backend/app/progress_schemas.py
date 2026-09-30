from datetime import datetime
from uuid import UUID
from pydantic import Field
from app.schemas import Schema


class Performance(Schema):
    answered_count: int = Field(default=0, ge=0)
    auto_graded_count: int = Field(default=0, ge=0)
    correct_count: int = Field(default=0, ge=0)
    accuracy_percent: float | None = Field(default=None, ge=0, le=100)


class TopicPerformance(Performance):
    slug: str
    name: str


class SkillPerformance(Performance):
    code: str
    name: str


class Overview(Schema):
    completed_quizzes: int
    completed_attempts: int
    questions_answered: int
    auto_graded_questions: int
    auto_graded_correct: int
    auto_graded_accuracy: float | None


class RecentAttempt(Performance):
    id: UUID
    quiz_id: int
    quiz_title: str
    submitted_at: datetime
    total_question_count: int
    objective_score: int
    objective_total: int


class ProgressRead(Schema):
    overview: Overview
    topics: list[TopicPerformance]
    skills: list[SkillPerformance]
    unattributed_topic: Performance
    unattributed_skill: Performance
    recent_attempts: list[RecentAttempt]

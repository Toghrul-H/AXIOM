from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from app.schemas import Schema, ShortText, NonBlank, PositiveId, AnswerCheck, ResponseKind

class QuizEntry(Schema):
    question_id: PositiveId
    points: int = Field(default=1,gt=0,le=1000,strict=True)

class QuizWrite(Schema):
    title: ShortText
    description: NonBlank | None = None
    status: Literal['DRAFT','ACTIVE','INACTIVE'] = 'DRAFT'
    questions: list[QuizEntry] = Field(default_factory=list,max_length=100)

    @model_validator(mode='after')
    def valid_questions(self):
        if len({q.question_id for q in self.questions}) != len(self.questions):
            raise ValueError('Each question may occur only once in a quiz.')
        if self.status == 'ACTIVE' and not self.questions:
            raise ValueError('An active quiz needs at least one question.')
        return self

class QuizEntryRead(QuizEntry):
    position: int

class QuizStaffRead(Schema):
    id: int
    title: str
    description: str | None
    status: str
    questions: list[QuizEntryRead]
    created_at: datetime
    updated_at: datetime

class QuizSummary(Schema):
    id: int
    title: str
    description: str | None
    status: str
    question_count: int
    total_points: int
    objective_points: int

class AttemptSummary(Schema):
    id: UUID
    quiz_id: int
    quiz_title: str
    status: str
    started_at: datetime
    submitted_at: datetime | None
    objective_score: int | None
    objective_total: int

class StudentOption(Schema):
    id: int
    text: str

class ActiveItem(Schema):
    id: int
    position: int
    points: int
    question_text: str
    topic_slug: str | None = None
    response_type: ResponseKind
    options: list[StudentOption]
    selected_option_ids: list[int]
    boolean_answer: bool | None
    free_response: str | None

class ActiveAttempt(AttemptSummary):
    items: list[ActiveItem]

class ReviewItem(ActiveItem):
    answered: bool
    auto_gradable: bool
    is_correct: bool | None
    points_awarded: int | None
    correct_option_ids: list[int]
    correct_boolean: bool | None
    expected_answer: str | None
    explanation: str | None

class AttemptReview(AttemptSummary):
    correct_count: int
    incorrect_count: int
    unanswered_objective_count: int
    ungraded_count: int
    items: list[ReviewItem]

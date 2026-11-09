from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

QuestionType = Literal["SHORT_TEXT", "LONG_TEXT", "SINGLE_CHOICE", "MULTIPLE_CHOICE", "YES_NO"]
Grade = Literal["1", "2", "3", "4", "5", "NOT_YET_GRADED"]
RESPONSIBILITIES = {"Teaching or assisting practice sessions", "Grading assignments", "Helping students", "Preparing learning materials", "Other"}


class VacancyWrite(BaseModel):
    course_name: str = Field(min_length=2, max_length=200)
    semester: str = Field(min_length=2, max_length=80)
    available_positions: int = Field(ge=0, le=1000)
    description: str = Field(min_length=2, max_length=10000)
    responsibilities: str = Field(min_length=2, max_length=10000)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    state: str = "DRAFT"

    @model_validator(mode="after")
    def dates_and_state(self):
        if self.state not in {"DRAFT", "OPEN", "CLOSED"}:
            raise ValueError("Invalid vacancy state")
        if self.opens_at and self.closes_at and self.opens_at >= self.closes_at:
            raise ValueError("Opening time must be before closing time")
        return self


class QuestionnaireQuestionWrite(BaseModel):
    id: int | None = Field(default=None, gt=0)
    title: str = Field(min_length=2, max_length=1000)
    question_type: QuestionType
    required: bool = False
    options: list[str] | None = None

    @model_validator(mode="after")
    def validate_options(self):
        if self.question_type in {"SINGLE_CHOICE", "MULTIPLE_CHOICE"}:
            if not self.options or len(self.options) < 2 or any(not option.strip() for option in self.options):
                raise ValueError("Choice questions need at least two non-empty options")
            if len({option.strip().casefold() for option in self.options}) != len(self.options):
                raise ValueError("Choice options must be distinct")
        elif self.options:
            raise ValueError("Only choice questions may define options")
        return self


class QuestionnaireQuestionRead(QuestionnaireQuestionWrite):
    id: int
    display_order: int


class QuestionnaireUpdate(BaseModel):
    questions: list[QuestionnaireQuestionWrite] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_titles(self):
        titles = [question.title.strip().casefold() for question in self.questions]
        if len(set(titles)) != len(titles):
            raise ValueError("Custom question titles must be distinct")
        return self


class VacancyRead(VacancyWrite):
    id: int
    applicant_count: int
    application_open: bool
    questionnaire: list[QuestionnaireQuestionRead] = Field(default_factory=list)


class StaffVacancyRead(VacancyRead):
    status_counts: dict[str, int]
    accepted_count: int
    remaining_positions: int
    questionnaire_locked: bool


class CustomAnswerRead(BaseModel):
    question_id: int
    question_title: str
    question_type: QuestionType
    answer: str | list[str] | bool | None
    display_order: int


class ApplicationWrite(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    neptun_code: str = Field(min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")
    lecture_grade: Grade
    practice_grade: Grade
    practice_teacher: str = Field(min_length=2, max_length=200)
    motivation: str = Field(min_length=10, max_length=10000)
    weekly_availability: int = Field(ge=0, le=168)
    preferred_responsibilities: list[str] = Field(min_length=1, max_length=5)
    relevant_experience: str | None = Field(default=None, max_length=10000)
    additional_comments: str | None = Field(default=None, max_length=10000)
    custom_answers: dict[int, str | list[str] | bool | None] = Field(default_factory=dict)

    @model_validator(mode="after")
    def responsibilities_are_supported(self):
        if any(answer not in RESPONSIBILITIES for answer in self.preferred_responsibilities):
            raise ValueError("Invalid preferred responsibility")
        if len(set(self.preferred_responsibilities)) != len(self.preferred_responsibilities):
            raise ValueError("Preferred responsibilities must be distinct")
        return self


class ApplicationRead(BaseModel):
    id: int
    vacancy_id: int
    full_name: str
    neptun_code: str
    lecture_grade: str | None = None
    practice_grade: str | None = None
    legacy_final_grade: str | None = None
    legacy_completion_semester: str | None = None
    practice_teacher: str | None = None
    motivation: str | None = None
    weekly_availability: int | None = None
    preferred_responsibilities: list[str] | None = None
    relevant_experience: str | None = None
    additional_comments: str | None = None
    custom_answers: list[CustomAnswerRead] = Field(default_factory=list)
    status: str
    submitted_at: datetime
    decision_at: datetime | None = None


class ApplicationStatusUpdate(BaseModel):
    status: Literal["UNDER_REVIEW", "ACCEPTED", "REJECTED"]


class NotificationRead(BaseModel):
    id: int
    title: str
    body: str
    link: str
    created_at: datetime
    model_config = {"from_attributes": True}

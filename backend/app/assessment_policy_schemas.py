"""Validated semester policies; descriptions are plain text, never executable rules."""
from datetime import date, time
from decimal import Decimal
from typing import Annotated, Literal, Self
from pydantic import Field, model_validator, field_validator
from app.schemas import Schema, NonBlank, ShortText

PolicyCode = Literal['SHORT_QUIZZES', 'MIDTERM', 'ENDTERM', 'COURSEWORK']
Score = Annotated[Decimal, Field(ge=0, le=100000, max_digits=8, decimal_places=2, allow_inf_nan=False)]

class PolicyWrite(Schema):
    topics: NonBlank | None = None
    assessment_mode: NonBlank | None = None
    duration_minutes: Annotated[int, Field(gt=0, le=10080, strict=True)] | None = None
    duration_description: NonBlank | None = None
    maximum_score: Score | None = None
    passing_score: Score | None = None
    assessment_count: Annotated[int, Field(gt=0, le=1000, strict=True)] | None = None
    success_criteria: NonBlank | None = None
    permitted_equipment: NonBlank | None = None
    retake_rules: NonBlank | None = None
    conduct_instructions: NonBlank | None = None
    preparation_instructions: NonBlank | None = None

    @model_validator(mode='after')
    def valid_scores(self) -> Self:
        if self.maximum_score is not None and self.passing_score is not None and self.passing_score > self.maximum_score:
            raise ValueError('Passing score cannot exceed the component maximum score')
        return self

class PolicyRead(PolicyWrite):
    code: PolicyCode

class GradeBoundary(Schema):
    grade: Annotated[int, Field(ge=1, le=5, strict=True)]
    minimum_score: Score

class RulesWrite(Schema):
    course_topics: NonBlank | None = None
    attendance_rules: NonBlank | None = None
    total_score_rules: NonBlank | None = None
    plus_points_maximum: Score | None = None
    plus_points_rules: NonBlank | None = None
    grade_boundaries: list[GradeBoundary] = Field(default_factory=list, max_length=5)

    @model_validator(mode='after')
    def ordered_boundaries(self) -> Self:
        rows = sorted(self.grade_boundaries, key=lambda row: row.grade)
        if rows and ([r.grade for r in rows] != [1,2,3,4,5] or rows[0].minimum_score != 0):
            raise ValueError('Configure all five grades, with grade 1 starting at zero, or leave boundaries empty')
        if any(a.minimum_score >= b.minimum_score for a,b in zip(rows, rows[1:])):
            raise ValueError('Grade minimum scores must strictly increase')
        return self

class RulesRead(RulesWrite):
    maximum_total_score: Decimal | None = None

class SubmissionDeadline(Schema):
    group_identifier: Annotated[str, Field(min_length=1, max_length=50)]
    deadline_date: date | None = None
    deadline_time: time | None = None
    venue: ShortText | None = None
    instructions: NonBlank | None = None

    @field_validator('group_identifier')
    @classmethod
    def trim_group(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Practice group cannot be blank')
        return value

    @field_validator('deadline_time')
    @classmethod
    def local_clock(cls, value):
        if value is not None and value.tzinfo is not None:
            raise ValueError('Use local campus clock times without UTC offsets')
        return value

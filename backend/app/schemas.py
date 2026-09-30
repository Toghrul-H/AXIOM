from datetime import datetime
from typing import Annotated, Literal, Self
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Code = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{0,39}$")]
PositiveId = Annotated[int, Field(gt=0, strict=True)]
Difficulty = Literal["easy", "medium", "hard"]
ResponseKind = Literal["FREE_RESPONSE", "SINGLE_CHOICE", "MULTIPLE_SELECT", "TRUE_FALSE"]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class OptionInput(Schema):
    id: PositiveId | None = None
    text: NonBlank
    is_correct: StrictBool = False


class QuestionCreate(Schema):
    topic_id: PositiveId
    title: ShortText | None = None
    difficulty: Difficulty
    response_type: ResponseKind
    skill_type: Code
    question_text: NonBlank
    expected_answer: NonBlank | None = None
    correct_boolean: StrictBool | None = None
    explanation: NonBlank | None = None
    is_active: StrictBool = True
    options: list[OptionInput] = Field(default_factory=list, max_length=20)
    problem_set_ids: list[PositiveId] = Field(default_factory=list, max_length=100)
    assessment_suitability_codes: list[Code] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_configuration(self) -> Self:
        for values in (self.problem_set_ids, self.assessment_suitability_codes):
            if len(values) != len(set(values)):
                raise ValueError("Associations must be unique.")
        option_ids = [o.id for o in self.options if o.id is not None]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("Option IDs must be unique.")
        if self.response_type in {"SINGLE_CHOICE", "MULTIPLE_SELECT"}:
            if len(self.options) < 2 or len({o.text for o in self.options}) != len(self.options):
                raise ValueError("Choice questions require 2–20 distinct, nonempty options.")
            count = sum(o.is_correct for o in self.options)
            if self.response_type == "SINGLE_CHOICE" and count != 1:
                raise ValueError("Single choice requires exactly one correct option.")
            if self.response_type == "MULTIPLE_SELECT" and count < 1:
                raise ValueError("Multiple select requires at least one correct option.")
            if self.expected_answer is not None or self.correct_boolean is not None:
                raise ValueError("Choice answers are stored only on the options.")
        else:
            if self.options:
                raise ValueError("Only choice questions may have options.")
            if self.response_type == "TRUE_FALSE":
                if self.correct_boolean is None or self.expected_answer is not None:
                    raise ValueError("True/false requires a boolean answer only.")
            elif self.expected_answer is None or self.correct_boolean is not None:
                raise ValueError("Free response requires a reference answer only.")
        return self


class QuestionPatch(Schema):
    topic_id: PositiveId | None = None
    title: ShortText | None = None
    difficulty: Difficulty | None = None
    response_type: ResponseKind | None = None
    skill_type: Code | None = None
    question_text: NonBlank | None = None
    expected_answer: NonBlank | None = None
    correct_boolean: StrictBool | None = None
    explanation: NonBlank | None = None
    is_active: StrictBool | None = None
    options: list[OptionInput] | None = Field(default=None, max_length=20)
    problem_set_ids: list[PositiveId] | None = Field(default=None, max_length=100)
    assessment_suitability_codes: list[Code] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        for field in self.model_fields_set - {"title", "expected_answer", "correct_boolean", "explanation"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        return self


class LookupRead(Schema):
    code: str
    label: str
    sort_order: int


class TopicParent(Schema):
    id: int
    name: str


class TopicRead(TopicParent):
    slug: str
    parent_id: int | None
    sort_order: int
    parent: TopicParent | None


class ProblemSetRead(Schema):
    id: int
    code: str
    name: str
    sort_order: int


class OptionRead(OptionInput):
    id: int
    position: int


class QuestionRead(Schema):
    id: int
    topic: TopicRead
    title: str | None
    difficulty: Difficulty
    response_type: ResponseKind
    skill_type: str
    question_text: str
    expected_answer: str | None
    correct_boolean: bool | None
    explanation: str | None
    is_active: bool
    options: list[OptionRead]
    problem_sets: list[ProblemSetRead]
    assessment_suitabilities: list[LookupRead]
    created_at: datetime
    updated_at: datetime


class QuestionPage(Schema):
    items: list[QuestionRead]
    total: int
    offset: int
    limit: int


class QuestionMetadata(Schema):
    topics: list[TopicRead]
    response_types: list[LookupRead]
    skill_types: list[LookupRead]
    problem_sets: list[ProblemSetRead]
    assessment_suitabilities: list[LookupRead]


class AnswerCheck(Schema):
    selected_option_ids: list[PositiveId] = Field(default_factory=list, max_length=20)
    boolean_answer: StrictBool | None = None
    free_response: NonBlank | None = None

    @model_validator(mode="after")
    def unique_choices(self) -> Self:
        if len(self.selected_option_ids) != len(set(self.selected_option_ids)):
            raise ValueError("Selected options must be unique.")
        return self


class AnswerFeedback(Schema):
    auto_gradable: bool
    is_correct: bool | None
    correct_option_ids: list[int]
    correct_boolean: bool | None
    expected_answer: str | None
    explanation: str | None
    message: str

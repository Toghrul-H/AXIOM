from datetime import datetime
from typing import Self

from pydantic import Field, model_validator

from app.schemas import NonBlank, PositiveId, Schema, ShortText


class ExamQuestionWrite(Schema):
    question_id: PositiveId
    points: int = Field(gt=0, le=1000, strict=True)


class ExamWriteBase(Schema):
    title: ShortText
    instructions: NonBlank | None = None
    assessment_configuration_id: PositiveId | None = None
    questions: list[ExamQuestionWrite] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_questions(self) -> Self:
        if len({entry.question_id for entry in self.questions}) != len(self.questions):
            raise ValueError("Each question may occur only once in an exam.")
        return self


class ExamCreate(ExamWriteBase):
    pass


class ExamPatch(Schema):
    title: ShortText | None = None
    instructions: NonBlank | None = None
    assessment_configuration_id: PositiveId | None = None
    questions: list[ExamQuestionWrite] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def valid_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title cannot be null.")
        if "questions" in self.model_fields_set:
            if self.questions is None:
                raise ValueError("questions cannot be null.")
            if len({entry.question_id for entry in self.questions}) != len(self.questions):
                raise ValueError("Each question may occur only once in an exam.")
        return self


class ExamQuestionRead(ExamQuestionWrite):
    position: int


class ExamRead(Schema):
    id: int
    title: str
    instructions: str | None
    status: str
    assessment_configuration_id: int | None
    created_by_id: int
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime
    questions: list[ExamQuestionRead]
    snapshot_available: bool

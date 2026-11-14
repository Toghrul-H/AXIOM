from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StringConstraints, model_validator

from app.schemas import NonBlank, PositiveId, Schema, ShortText

DocumentText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ExamHeaderSettings(Schema):
    institution_name: DocumentText = "Eötvös Loránd University"
    course_name: DocumentText = "Discrete Mathematics I"
    instructor_name: DocumentText | None = None
    document_date: date | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=600, strict=True)


class ExamLayoutSettings(Schema):
    paper_size: Literal["A4"] = "A4"
    margins: Literal["compact", "normal", "wide"] = "normal"
    question_spacing: Literal["compact", "normal", "spacious"] = "normal"
    page_numbering: StrictBool = True


class ExamStudentFields(Schema):
    show_name: StrictBool = True
    show_neptun_code: StrictBool = True
    show_date: StrictBool = True


class ExamQuestionSettings(Schema):
    show_points: StrictBool = True
    answer_space: Literal["none", "small", "medium", "large"] = "medium"
    numbering_enabled: StrictBool = True
    page_break_before_question_ids: list[PositiveId] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_page_breaks(self) -> Self:
        if len(set(self.page_break_before_question_ids)) != len(self.page_break_before_question_ids):
            raise ValueError("Page-break question IDs must be unique.")
        return self


class ExamDocumentSettings(Schema):
    header: ExamHeaderSettings = Field(default_factory=ExamHeaderSettings)
    layout: ExamLayoutSettings = Field(default_factory=ExamLayoutSettings)
    student_fields: ExamStudentFields = Field(default_factory=ExamStudentFields)
    questions: ExamQuestionSettings = Field(default_factory=ExamQuestionSettings)


class ExamQuestionWrite(Schema):
    question_id: PositiveId
    points: int = Field(gt=0, le=1000, strict=True)


class ExamWriteBase(Schema):
    title: ShortText
    instructions: NonBlank | None = None
    assessment_configuration_id: PositiveId | None = None
    questions: list[ExamQuestionWrite] = Field(default_factory=list, max_length=100)
    document_settings: ExamDocumentSettings = Field(default_factory=ExamDocumentSettings)

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
    document_settings: ExamDocumentSettings | None = None

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
        if "document_settings" in self.model_fields_set and self.document_settings is None:
            raise ValueError("document_settings cannot be null.")
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
    document_settings: ExamDocumentSettings
    snapshot_available: bool

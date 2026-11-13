from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StringConstraints, model_validator

from app.schemas import NonBlank, PositiveId, Schema, ShortText

VariantLabel = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Z][A-Z0-9_-]{0,15}$")]
VariantSeed = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
DocumentText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class PracticeSheetHeaderSettings(Schema):
    institution_name: DocumentText = "Eötvös Loránd University"
    course_name: DocumentText = "Discrete Mathematics I"
    instructor_name: DocumentText | None = None
    document_date: date | None = None
    logo_visible: StrictBool = True


class PracticeSheetLayoutSettings(Schema):
    paper_size: Literal["A4"] = "A4"
    margins: Literal["compact", "normal", "wide"] = "normal"
    question_spacing: Literal["compact", "normal", "spacious"] = "normal"


class PracticeSheetQuestionSettings(Schema):
    show_points: StrictBool = True
    answer_space: Literal["none", "small", "medium", "large"] = "medium"
    numbering_enabled: StrictBool = True
    page_break_before_question_ids: list[PositiveId] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_page_breaks(self) -> Self:
        if len(set(self.page_break_before_question_ids)) != len(self.page_break_before_question_ids):
            raise ValueError("Page-break question IDs must be unique.")
        return self


class PracticeSheetDocumentSettings(Schema):
    header: PracticeSheetHeaderSettings = Field(default_factory=PracticeSheetHeaderSettings)
    layout: PracticeSheetLayoutSettings = Field(default_factory=PracticeSheetLayoutSettings)
    questions: PracticeSheetQuestionSettings = Field(default_factory=PracticeSheetQuestionSettings)


class PracticeSheetQuestionWrite(Schema):
    question_id: PositiveId
    points: int | None = Field(default=None, gt=0, le=1000, strict=True)


class PracticeSheetWriteBase(Schema):
    title: ShortText
    instructions: NonBlank | None = None
    questions: list[PracticeSheetQuestionWrite] = Field(default_factory=list, max_length=100)
    document_settings: PracticeSheetDocumentSettings = Field(default_factory=PracticeSheetDocumentSettings)

    @model_validator(mode="after")
    def unique_questions(self) -> Self:
        if len({entry.question_id for entry in self.questions}) != len(self.questions):
            raise ValueError("Each question may occur only once in a practice sheet.")
        return self


class PracticeSheetCreate(PracticeSheetWriteBase):
    pass


class PracticeSheetPatch(Schema):
    title: ShortText | None = None
    instructions: NonBlank | None = None
    questions: list[PracticeSheetQuestionWrite] | None = Field(default=None, max_length=100)
    document_settings: PracticeSheetDocumentSettings | None = None

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
                raise ValueError("Each question may occur only once in a practice sheet.")
        if "document_settings" in self.model_fields_set and self.document_settings is None:
            raise ValueError("document_settings cannot be null.")
        return self


class VariantGenerate(Schema):
    labels: list[VariantLabel] = Field(min_length=1, max_length=26)
    seed: VariantSeed
    question_count: int | None = Field(default=None, gt=0, le=100)

    @model_validator(mode="after")
    def unique_labels(self) -> Self:
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("Variant labels must be unique.")
        return self


class PracticeSheetQuestionRead(PracticeSheetQuestionWrite):
    position: int


class PracticeSheetVariantRead(Schema):
    id: int
    label: str
    seed: str
    generator_version: str
    generated_at: datetime
    question_count: int


class PracticeSheetRead(Schema):
    id: int
    title: str
    instructions: str | None
    status: str
    created_by_id: int
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime
    document_settings: PracticeSheetDocumentSettings
    questions: list[PracticeSheetQuestionRead]
    variants: list[PracticeSheetVariantRead]

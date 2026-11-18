"""Validated API representations for course content."""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from app.schemas import PositiveId, Schema

CourseTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
CourseSlug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=1, max_length=120)]
LessonContent = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50000)]
CourseStatus = Literal["draft", "published"]
MaterialDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]


class QuestionLinkWrite(Schema):
    question_id: PositiveId


class ChapterCreate(Schema):
    title: CourseTitle
    slug: CourseSlug
    position: int = Field(ge=0, strict=True)


class ChapterPatch(Schema):
    title: CourseTitle | None = None
    slug: CourseSlug | None = None
    position: int | None = Field(default=None, ge=0, strict=True)

    @model_validator(mode="after")
    def nonempty(self) -> Self:
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Provide non-null chapter fields to update.")
        return self


class LessonCreate(Schema):
    chapter_id: PositiveId
    title: CourseTitle
    slug: CourseSlug
    content: LessonContent
    position: int = Field(ge=0, strict=True)
    questions: list[QuestionLinkWrite] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_questions(self) -> Self:
        if len({item.question_id for item in self.questions}) != len(self.questions):
            raise ValueError("Each question may occur only once in a lesson.")
        return self


class LessonPatch(Schema):
    chapter_id: PositiveId | None = None
    title: CourseTitle | None = None
    slug: CourseSlug | None = None
    content: LessonContent | None = None
    position: int | None = Field(default=None, ge=0, strict=True)
    questions: list[QuestionLinkWrite] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def valid_patch(self) -> Self:
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Provide non-null lesson fields to update.")
        if self.questions is not None and len({item.question_id for item in self.questions}) != len(self.questions):
            raise ValueError("Each question may occur only once in a lesson.")
        return self


class OrderUpdate(Schema):
    ids: list[PositiveId] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        if len(self.ids) != len(set(self.ids)):
            raise ValueError("Ordering IDs must be unique.")
        return self


class MaterialCreate(Schema):
    title: CourseTitle
    description: MaterialDescription | None = None
    chapter_id: PositiveId | None = None
    lesson_id: PositiveId | None = None
    position: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def exactly_one_parent(self) -> Self:
        if (self.chapter_id is None) == (self.lesson_id is None):
            raise ValueError("A material must belong to exactly one chapter or lesson.")
        return self


class MaterialPatch(Schema):
    title: CourseTitle | None = None
    description: MaterialDescription | None = None
    position: int | None = Field(default=None, ge=0, strict=True)

    @model_validator(mode="after")
    def nonempty(self) -> Self:
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Provide non-null material fields to update.")
        return self


class MaterialRead(Schema):
    id: int
    chapter_id: int | None
    lesson_id: int | None
    title: str
    description: str | None
    filename: str | None
    media_type: str | None
    size_bytes: int | None
    sha256: str | None
    storage_ready: bool
    status: CourseStatus
    position: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class MaterialPublicRead(Schema):
    id: int
    title: str
    description: str | None
    filename: str
    media_type: str
    size_bytes: int
    position: int


class QuestionLinkRead(Schema):
    question_id: int
    position: int


class LessonRead(Schema):
    id: int
    chapter_id: int
    title: str
    slug: str
    content: str
    position: int
    status: CourseStatus | None = None
    created_at: datetime
    updated_at: datetime
    questions: list[QuestionLinkRead]
    materials: list[MaterialPublicRead]


class ChapterRead(Schema):
    id: int
    title: str
    slug: str
    position: int
    status: CourseStatus | None = None
    created_at: datetime
    updated_at: datetime
    lessons: list[LessonRead]
    materials: list[MaterialPublicRead]

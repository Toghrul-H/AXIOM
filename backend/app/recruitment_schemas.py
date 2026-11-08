from datetime import datetime
from pydantic import BaseModel, Field, model_validator


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


class VacancyRead(VacancyWrite):
    id: int
    applicant_count: int
    application_open: bool
    model_config = {"from_attributes": True}


class ApplicationWrite(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    neptun_code: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9]+$")
    final_grade: str | None = Field(default=None, max_length=20)
    practice_teacher: str = Field(min_length=2, max_length=200)
    completion_semester: str = Field(min_length=2, max_length=80)
    motivation: str = Field(min_length=10, max_length=10000)
    teaching_experience: str = Field(min_length=2, max_length=10000)
    responsibility_interest: str = Field(min_length=2, max_length=10000)
    additional_information: str | None = Field(default=None, max_length=10000)


class ApplicationRead(ApplicationWrite):
    id: int
    vacancy_id: int
    status: str
    submitted_at: datetime
    model_config = {"from_attributes": True}


class NotificationRead(BaseModel):
    id: int
    title: str
    body: str
    link: str
    created_at: datetime
    model_config = {"from_attributes": True}

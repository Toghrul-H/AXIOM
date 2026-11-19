from datetime import date, datetime

from pydantic import Field, StrictBool, field_validator

from app.schemas import Schema, ShortText


class PersonalTaskWrite(Schema):
    title: ShortText
    due_date: date | None = None
    completed: StrictBool = False

    @field_validator("due_date")
    @classmethod
    def safe_due_date(cls, value: date | None) -> date | None:
        if value is not None and not (date(2000, 1, 1) <= value <= date(2100, 12, 31)):
            raise ValueError("Due date must be between 2000 and 2100")
        return value


class PersonalTaskRead(Schema):
    id: int
    title: str
    due_date: date | None
    completed: bool
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

from datetime import date as CalendarDate, datetime, time
from typing import Annotated, Literal, Self
from pydantic import Field, StringConstraints, field_validator, model_validator
from app.schemas import Schema, ShortText, NonBlank

Term = Literal['SPRING', 'FALL']
EventType = Literal['MIDTERM', 'ENDTERM', 'SHORT_QUIZ_RETAKE', 'TEST_RETAKE', 'COURSEWORK_PUBLICATION', 'COURSEWORK_HAND_IN', 'COURSEWORK_RETAKE_PUBLICATION', 'COURSEWORK_RETAKE_HAND_IN']
Year = Annotated[int, Field(ge=1900, le=9998, strict=True)]
GroupIdentifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]

class ConfigurationCreate(Schema):
    academic_year_start: Year
    term: Term
    display_label: ShortText

class ConfigurationPatch(Schema):
    academic_year_start: Year | None = None
    term: Term | None = None
    display_label: ShortText | None = None

    @model_validator(mode='after')
    def no_nulls(self) -> Self:
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('Configuration metadata cannot be null')
        return self

class EventWrite(Schema):
    event_type: EventType
    date: CalendarDate | None = None
    start_time: time | None = None
    end_time: time | None = None
    venue: ShortText | None = None
    notes: NonBlank | None = None
    document_date: CalendarDate | None = None
    latest_arrival_time: time | None = None

    @field_validator('start_time', 'end_time', 'latest_arrival_time')
    @classmethod
    def local_clock(cls, value):
        if value is not None and value.tzinfo is not None:
            raise ValueError('Use local campus clock times without UTC offsets')
        return value

    @model_validator(mode='after')
    def ordered_times(self) -> Self:
        if self.start_time is not None and self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError('End time must be later than start time')
        return self

class RoomWrite(Schema):
    room: ShortText
    groups: list[GroupIdentifier] = Field(min_length=1, max_length=500)

    @field_validator('groups')
    @classmethod
    def unique_groups(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('Practice groups must be unique within a room')
        return value

class GroupRead(Schema):
    identifier: str

class RoomRead(Schema):
    id: int
    room: str
    groups: list[GroupRead]

class EventRead(EventWrite):
    id: int
    created_at: datetime
    updated_at: datetime
    last_modified_by_id: int | None
    rooms: list[RoomRead]

class ConfigurationRead(ConfigurationCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    last_modified_by_id: int | None

class ConfigurationDetail(ConfigurationRead):
    events: list[EventRead]

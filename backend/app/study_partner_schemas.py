from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


StudyFormat = Literal["ONLINE", "IN_PERSON", "EITHER"]
TopicPurpose = Literal["WANT_TO_STUDY", "CAN_HELP"]
RequestStatus = Literal["PENDING", "ACCEPTED", "DECLINED", "CANCELLED"]


def _clean_short(value: str) -> str:
    value = value.strip()
    if any(ord(character) < 32 for character in value):
        raise ValueError("Control characters are not permitted")
    return value


class StudyPartnerTopicWrite(BaseModel):
    topic_id: int = Field(gt=0)
    purpose: TopicPurpose


class StudyPartnerTopicRead(StudyPartnerTopicWrite):
    name: str
    slug: str


class AvailabilitySlot(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_minute: int = Field(ge=0, le=1439)
    end_minute: int = Field(ge=1, le=1440)

    @model_validator(mode="after")
    def ends_after_start(self):
        if self.end_minute <= self.start_minute:
            raise ValueError("Availability must end after it starts")
        return self


class StudyPartnerProfileWrite(BaseModel):
    display_name: str = Field(min_length=2, max_length=60)
    is_participating: bool = False
    is_discoverable: bool = False
    study_format: StudyFormat = "EITHER"
    introduction: str | None = Field(default=None, max_length=500)
    topics: list[StudyPartnerTopicWrite] = Field(default_factory=list, max_length=100)
    availability: list[AvailabilitySlot] = Field(default_factory=list, max_length=28)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        value = _clean_short(value)
        if len(value) < 2:
            raise ValueError("Display name must contain at least two characters")
        return value

    @field_validator("introduction")
    @classmethod
    def clean_introduction(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if any(ord(character) < 32 and character not in "\n\r\t" for character in value):
            raise ValueError("Control characters are not permitted")
        return value or None

    @model_validator(mode="after")
    def profile_is_consistent(self):
        if self.is_discoverable and not self.is_participating:
            raise ValueError("Only participating profiles can be discoverable")
        preferences = [(topic.topic_id, topic.purpose) for topic in self.topics]
        if len(set(preferences)) != len(preferences):
            raise ValueError("Topic preferences must be unique")
        slots = sorted(self.availability, key=lambda slot: (slot.weekday, slot.start_minute, slot.end_minute))
        for previous, current in zip(slots, slots[1:]):
            if previous.weekday == current.weekday and current.start_minute < previous.end_minute:
                raise ValueError("Availability slots may not overlap")
        return self


class StudyPartnerProfileRead(BaseModel):
    exists: bool
    display_name: str | None = None
    is_participating: bool = False
    is_discoverable: bool = False
    study_format: StudyFormat = "EITHER"
    introduction: str | None = None
    topics: list[StudyPartnerTopicRead] = Field(default_factory=list)
    availability: list[AvailabilitySlot] = Field(default_factory=list)


class StudyPartnerPublicRead(BaseModel):
    profile_id: int
    display_name: str
    introduction: str | None = None
    study_format: StudyFormat
    shared_study_topics: list[StudyPartnerTopicRead] = Field(default_factory=list)
    complementary_topics: list[StudyPartnerTopicRead] = Field(default_factory=list)
    has_compatible_availability: bool


class StudyPartnerRequestCreate(BaseModel):
    recipient_profile_id: int = Field(gt=0)


class StudyPartnerRequestCounterpart(BaseModel):
    profile_id: int
    display_name: str


class StudyPartnerRequestRead(BaseModel):
    id: int
    status: RequestStatus
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    counterpart: StudyPartnerRequestCounterpart


class StudyPartnerBlockCreate(BaseModel):
    blocked_user_id: int = Field(gt=0)


class StudyPartnerBlockRead(BaseModel):
    blocked_user_id: int
    created_at: datetime


class StudyPartnerMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be empty")
        if any(ord(character) < 32 and character not in "\n\r\t" for character in value):
            raise ValueError("Control characters are not permitted")
        return value


class StudyPartnerMessageRead(BaseModel):
    id: int
    sender_user_id: int
    content: str
    created_at: datetime


class StudyPartnerChatRead(BaseModel):
    request_id: int
    counterpart: StudyPartnerRequestCounterpart
    last_message_preview: str | None = None
    last_message_at: datetime | None = None

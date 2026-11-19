from datetime import datetime
from typing import Literal
from pydantic import Field, field_validator
from app.schemas import Schema, NonBlank, ShortText

Category = Literal["IMPORTANT", "GENERAL"]

class AnnouncementWrite(Schema):
    title: ShortText
    body: NonBlank
    category: Category = "GENERAL"
    link: str | None = Field(default=None, max_length=240)
    pinned: bool = False
    @field_validator("link")
    @classmethod
    def internal_link(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not value.startswith("/") or value.startswith("//") or "\\" in value or any(ord(char) < 32 for char in value):
            raise ValueError("Announcement links must be safe internal paths")
        return value

class AnnouncementRead(Schema):
    id: int
    title: str
    body: str
    category: Category
    link: str | None
    pinned: bool
    status: str | None = None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    read_at: datetime | None = None

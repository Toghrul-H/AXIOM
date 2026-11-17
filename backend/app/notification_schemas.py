from datetime import datetime
from pydantic import BaseModel, Field


NotificationValue = str | int | bool | None


class NotificationRead(BaseModel):
    id: int
    kind: str
    payload: dict[str, NotificationValue]
    link: str
    created_at: datetime
    read_at: datetime | None = None

    model_config = {"from_attributes": True}


class NotificationPage(BaseModel):
    items: list[NotificationRead]
    next_cursor: str | None = None


class UnreadCount(BaseModel):
    count: int = Field(ge=0)

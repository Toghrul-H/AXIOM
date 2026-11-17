from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.auth_models import User
from app.database import get_session
from app.notification_schemas import NotificationPage, NotificationRead, UnreadCount
from app.services.notifications import list_notifications, mark_all_read, mark_read, unread_count


router = APIRouter(prefix="/notifications", tags=["Notifications"])
DB = Annotated[Session, Depends(get_session)]
Identity = Annotated[User, Depends(get_current_user)]
Id = Annotated[int, Path(gt=0)]


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("", response_model=NotificationPage)
def notifications(
    session: DB,
    actor: Identity,
    response: Response,
    cursor: str | None = Query(default=None, min_length=1, max_length=256),
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
):
    no_store(response)
    items, next_cursor = list_notifications(session, actor.id, limit=limit, cursor=cursor)
    return {"items": items, "next_cursor": next_cursor}


@router.get("/unread-count", response_model=UnreadCount)
def count_unread(session: DB, actor: Identity, response: Response):
    no_store(response)
    return {"count": unread_count(session, actor.id)}


@router.post("/{notification_id}/read", response_model=NotificationRead)
def read(notification_id: Id, session: DB, actor: Identity, response: Response):
    no_store(response)
    notification = mark_read(session, actor.id, notification_id)
    session.commit()
    session.refresh(notification)
    return notification


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def read_all(session: DB, actor: Identity, response: Response):
    no_store(response)
    mark_all_read(session, actor.id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})

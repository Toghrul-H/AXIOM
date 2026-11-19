from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import manager_user, require_roles, student_user
from app.auth_models import User
from app.database import get_session
from app.announcement_models import CourseAnnouncement, CourseAnnouncementRead
from app.announcement_schemas import AnnouncementRead, AnnouncementWrite
from app.services.notifications import create_notifications, eligible_student_ids

router = APIRouter(tags=["Course announcements"])
DB = Annotated[Session, Depends(get_session)]
Manager = Annotated[User, Depends(manager_user)]
Student = Annotated[User, Depends(student_user)]
StudentPreview = Annotated[User, Depends(require_roles("STUDENT", "LECTURER", "ADMIN"))]
Id = Annotated[int, Path(gt=0)]

def _announcement(session, identifier):
    value = session.get(CourseAnnouncement, identifier)
    if value is None:
        raise HTTPException(404, "Announcement not found")
    return value

def _read(value, *, status_value=None, read_at=None):
    return {"id":value.id,"title":value.title,"body":value.body,"category":value.category,"link":value.link,"pinned":value.pinned,"status":status_value,"published_at":value.published_at,"created_at":value.created_at,"updated_at":value.updated_at,"read_at":read_at}

@router.get("/announcements", response_model=list[AnnouncementRead])
def managed(session: DB, actor: Manager):
    return [_read(item, status_value=item.status) for item in session.scalars(select(CourseAnnouncement).order_by(CourseAnnouncement.pinned.desc(), CourseAnnouncement.created_at.desc(), CourseAnnouncement.id.desc()))]

@router.post("/announcements", response_model=AnnouncementRead, status_code=201)
def create(payload: AnnouncementWrite, session: DB, actor: Manager):
    value = CourseAnnouncement(**payload.model_dump(), created_by_id=actor.id)
    session.add(value); session.commit(); session.refresh(value)
    return _read(value, status_value=value.status)

@router.put("/announcements/{announcement_id}", response_model=AnnouncementRead)
def update(announcement_id: Id, payload: AnnouncementWrite, session: DB, actor: Manager):
    value = _announcement(session, announcement_id)
    if value.status == "published": raise HTTPException(409, "Published announcements cannot be edited")
    for field, item in payload.model_dump().items(): setattr(value, field, item)
    session.commit(); session.refresh(value)
    return _read(value, status_value=value.status)

@router.post("/announcements/{announcement_id}/publish", response_model=AnnouncementRead)
def publish(announcement_id: Id, session: DB, actor: Manager):
    value = _announcement(session, announcement_id)
    if value.status != "published":
        value.status = "published"; value.published_at = datetime.now(timezone.utc)
        create_notifications(session, recipient_user_ids=eligible_student_ids(session), actor_user_id=actor.id, kind="COURSE_ANNOUNCEMENT_PUBLISHED", dedupe_key=f"course-announcement:{value.id}:published", payload={"title":"New course announcement", "resource_id":value.id}, link="/student")
    session.commit(); session.refresh(value)
    return _read(value, status_value=value.status)

@router.post("/announcements/{announcement_id}/unpublish", response_model=AnnouncementRead)
def unpublish(announcement_id: Id, session: DB, actor: Manager):
    value = _announcement(session, announcement_id); value.status = "draft"; session.commit(); session.refresh(value)
    return _read(value, status_value=value.status)

@router.delete("/announcements/{announcement_id}", status_code=204)
def delete(announcement_id: Id, session: DB, actor: Manager):
    session.delete(_announcement(session, announcement_id)); session.commit()

@router.get("/student/announcements", response_model=list[AnnouncementRead])
def student_list(session: DB, actor: StudentPreview):
    rows = session.execute(select(CourseAnnouncement, CourseAnnouncementRead.read_at).outerjoin(CourseAnnouncementRead, (CourseAnnouncementRead.announcement_id == CourseAnnouncement.id) & (CourseAnnouncementRead.user_id == actor.id)).where(CourseAnnouncement.status == "published").order_by(CourseAnnouncement.pinned.desc(), CourseAnnouncement.published_at.desc(), CourseAnnouncement.id.desc()).limit(20)).all()
    return [_read(value, read_at=read_at) for value, read_at in rows]

@router.post("/student/announcements/{announcement_id}/read", response_model=AnnouncementRead)
def mark_read(announcement_id: Id, session: DB, actor: Student):
    value = session.scalar(select(CourseAnnouncement).where(CourseAnnouncement.id == announcement_id, CourseAnnouncement.status == "published"))
    if value is None: raise HTTPException(404, "Announcement not found")
    row = session.scalar(select(CourseAnnouncementRead).where(CourseAnnouncementRead.announcement_id == value.id, CourseAnnouncementRead.user_id == actor.id))
    if row is None:
        row = CourseAnnouncementRead(announcement_id=value.id, user_id=actor.id); session.add(row); session.commit(); session.refresh(row)
    return _read(value, read_at=row.read_at)

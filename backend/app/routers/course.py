from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.auth import manager_user, student_user
from app.auth_models import User
from app.course_schemas import ChapterCreate, ChapterPatch, ChapterRead, LessonCreate, LessonPatch, LessonRead, OrderUpdate
from app.database import get_session
from app.services import course

router = APIRouter(prefix="/course", tags=["Course"])
DB = Annotated[Session, Depends(get_session)]
Manager = Annotated[User, Depends(manager_user)]
Student = Annotated[User, Depends(student_user)]
Id = Annotated[int, Path(gt=0)]


@router.get("/chapters", response_model=list[ChapterRead], response_model_exclude_none=True)
def chapters(session: DB, actor: Student):
    return course.list_chapters(session, published_only=True)


@router.get("/lessons/{lesson_id}", response_model=LessonRead, response_model_exclude_none=True)
def lesson(lesson_id: Id, session: DB, actor: Student):
    return course.published_lesson(session, lesson_id)


@router.get("/manage/chapters", response_model=list[ChapterRead])
def managed_chapters(session: DB, actor: Manager):
    return course.list_chapters(session, published_only=False)


@router.post("/chapters", response_model=ChapterRead, status_code=status.HTTP_201_CREATED)
def create_chapter(payload: ChapterCreate, session: DB, actor: Manager):
    return course.read_chapter(course.create_chapter(session, payload), include_status=True)


@router.put("/chapters/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_chapters(payload: OrderUpdate, session: DB, actor: Manager):
    course.reorder_chapters(session, payload.ids)


@router.patch("/chapters/{chapter_id}", response_model=ChapterRead)
def update_chapter(chapter_id: Id, payload: ChapterPatch, session: DB, actor: Manager):
    return course.read_chapter(course.update_chapter(session, chapter_id, payload), include_status=True)


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(chapter_id: Id, session: DB, actor: Manager):
    course.delete_chapter(session, chapter_id)


@router.post("/chapters/{chapter_id}/publish", response_model=ChapterRead)
def publish_chapter(chapter_id: Id, session: DB, actor: Manager):
    return course.read_chapter(course.publish_chapter(session, chapter_id), include_status=True)


@router.post("/chapters/{chapter_id}/unpublish", response_model=ChapterRead)
def unpublish_chapter(chapter_id: Id, session: DB, actor: Manager):
    return course.read_chapter(course.unpublish_chapter(session, chapter_id), include_status=True)


@router.post("/lessons", response_model=LessonRead, status_code=status.HTTP_201_CREATED)
def create_lesson(payload: LessonCreate, session: DB, actor: Manager):
    return course.read_lesson(course.create_lesson(session, payload), include_status=True)


@router.patch("/lessons/{lesson_id}", response_model=LessonRead)
def update_lesson(lesson_id: Id, payload: LessonPatch, session: DB, actor: Manager):
    return course.read_lesson(course.update_lesson(session, lesson_id, payload), include_status=True)


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lesson(lesson_id: Id, session: DB, actor: Manager):
    course.delete_lesson(session, lesson_id)


@router.post("/lessons/{lesson_id}/publish", response_model=LessonRead)
def publish_lesson(lesson_id: Id, session: DB, actor: Manager):
    return course.read_lesson(course.publish_lesson(session, lesson_id), include_status=True)


@router.post("/lessons/{lesson_id}/unpublish", response_model=LessonRead)
def unpublish_lesson(lesson_id: Id, session: DB, actor: Manager):
    return course.read_lesson(course.unpublish_lesson(session, lesson_id), include_status=True)


@router.put("/chapters/{chapter_id}/lessons/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_lessons(chapter_id: Id, payload: OrderUpdate, session: DB, actor: Manager):
    course.reorder_lessons(session, chapter_id, payload.ids)

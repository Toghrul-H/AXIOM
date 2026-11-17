"""Transactional course-content operations."""

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.course_models import CourseChapter, CourseLesson, CourseLessonQuestion
from app.course_schemas import ChapterCreate, ChapterPatch, LessonCreate, LessonPatch
from app.models import Question


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Conflicting course content") from None


def _flush(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Conflicting course content") from None


def _chapter(session: Session, chapter_id: int, *, lock: bool = False) -> CourseChapter:
    statement = select(CourseChapter).where(CourseChapter.id == chapter_id)
    if lock:
        statement = statement.with_for_update()
    chapter = session.scalar(statement)
    if chapter is None:
        raise HTTPException(404, "Chapter not found")
    return chapter


def _lesson(session: Session, lesson_id: int, *, lock: bool = False) -> CourseLesson:
    statement = select(CourseLesson).where(CourseLesson.id == lesson_id)
    if lock:
        statement = statement.with_for_update()
    lesson = session.scalar(statement)
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    return lesson


def _questions(session: Session, ids: list[int]) -> None:
    if not ids:
        return
    found = session.scalars(select(Question.id).where(Question.id.in_(ids), Question.is_active.is_(True))).all()
    if len(found) != len(ids):
        raise HTTPException(422, "Lessons require active questions")


def _replace_questions(session: Session, lesson: CourseLesson, ids: list[int]) -> None:
    _questions(session, ids)
    lesson.questions.clear()
    session.flush()
    lesson.questions = [CourseLessonQuestion(question_id=question_id, position=index) for index, question_id in enumerate(ids)]


def read_lesson(lesson: CourseLesson, *, include_status: bool) -> dict:
    result = {
        "id": lesson.id, "chapter_id": lesson.chapter_id, "title": lesson.title, "slug": lesson.slug,
        "content": lesson.content, "position": lesson.position, "created_at": lesson.created_at,
        "updated_at": lesson.updated_at,
        "questions": [{"question_id": item.question_id, "position": item.position} for item in lesson.questions],
    }
    if include_status:
        result["status"] = lesson.status
    return result


def read_chapter(chapter: CourseChapter, *, include_status: bool, published_only: bool = False) -> dict:
    lessons = [item for item in chapter.lessons if not published_only or item.status == "published"]
    result = {
        "id": chapter.id, "title": chapter.title, "slug": chapter.slug, "position": chapter.position,
        "created_at": chapter.created_at, "updated_at": chapter.updated_at,
        "lessons": [read_lesson(item, include_status=include_status) for item in lessons],
    }
    if include_status:
        result["status"] = chapter.status
    return result


def list_chapters(session: Session, *, published_only: bool) -> list[dict]:
    statement = select(CourseChapter).options(selectinload(CourseChapter.lessons).selectinload(CourseLesson.questions))
    if published_only:
        statement = statement.where(CourseChapter.status == "published")
    chapters = session.scalars(statement.order_by(CourseChapter.position, CourseChapter.id)).all()
    return [read_chapter(item, include_status=not published_only, published_only=published_only) for item in chapters]


def published_lesson(session: Session, lesson_id: int) -> dict:
    statement = (
        select(CourseLesson).join(CourseChapter)
        .where(CourseLesson.id == lesson_id, CourseLesson.status == "published", CourseChapter.status == "published")
        .options(selectinload(CourseLesson.questions))
    )
    lesson = session.scalar(statement)
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    return read_lesson(lesson, include_status=False)


def create_chapter(session: Session, payload: ChapterCreate) -> CourseChapter:
    chapter = CourseChapter(**payload.model_dump())
    session.add(chapter)
    _commit(session)
    session.refresh(chapter)
    return chapter


def update_chapter(session: Session, chapter_id: int, payload: ChapterPatch) -> CourseChapter:
    chapter = _chapter(session, chapter_id)
    for name, value in payload.model_dump().items():
        setattr(chapter, name, value)
    _commit(session)
    session.refresh(chapter)
    return chapter


def publish_chapter(session: Session, chapter_id: int) -> CourseChapter:
    chapter = _chapter(session, chapter_id)
    chapter.status = "published"
    _commit(session)
    session.refresh(chapter)
    return chapter


def unpublish_chapter(session: Session, chapter_id: int) -> CourseChapter:
    chapter = _chapter(session, chapter_id)
    chapter.status = "draft"
    _commit(session)
    session.refresh(chapter)
    return chapter


def reorder_chapters(session: Session, ids: list[int]) -> None:
    current = session.scalars(select(CourseChapter).order_by(CourseChapter.id).with_for_update()).all()
    if {item.id for item in current} != set(ids):
        raise HTTPException(422, "Chapter ordering must include every chapter exactly once")
    # Move every row beyond the current range before assigning dense positions.
    # This avoids transient UNIQUE(position) collisions for legacy/gapped order values.
    offset = max(item.position for item in current) + len(current) + 1
    session.execute(update(CourseChapter).values(position=CourseChapter.position + offset))
    session.expire_all()
    for position, chapter_id in enumerate(ids):
        session.get(CourseChapter, chapter_id).position = position
    _commit(session)


def create_lesson(session: Session, payload: LessonCreate) -> CourseLesson:
    _chapter(session, payload.chapter_id)
    lesson = CourseLesson(**payload.model_dump(exclude={"questions"}))
    session.add(lesson)
    _flush(session)
    _replace_questions(session, lesson, [item.question_id for item in payload.questions])
    _commit(session)
    session.refresh(lesson)
    return lesson


def update_lesson(session: Session, lesson_id: int, payload: LessonPatch) -> CourseLesson:
    lesson = _lesson(session, lesson_id)
    values = payload.model_dump(exclude_unset=True, exclude={"questions"})
    if "chapter_id" in values:
        _chapter(session, values["chapter_id"])
    for name, value in values.items():
        setattr(lesson, name, value)
    if "questions" in payload.model_fields_set:
        _replace_questions(session, lesson, [item.question_id for item in payload.questions or []])
    _commit(session)
    session.refresh(lesson)
    return lesson


def publish_lesson(session: Session, lesson_id: int) -> CourseLesson:
    lesson = _lesson(session, lesson_id)
    lesson.status = "published"
    _commit(session)
    session.refresh(lesson)
    return lesson


def unpublish_lesson(session: Session, lesson_id: int) -> CourseLesson:
    lesson = _lesson(session, lesson_id)
    lesson.status = "draft"
    _commit(session)
    session.refresh(lesson)
    return lesson


def reorder_lessons(session: Session, chapter_id: int, ids: list[int]) -> None:
    _chapter(session, chapter_id, lock=True)
    current = session.scalars(select(CourseLesson).where(CourseLesson.chapter_id == chapter_id).order_by(CourseLesson.id).with_for_update()).all()
    if {item.id for item in current} != set(ids):
        raise HTTPException(422, "Lesson ordering must include every lesson in the chapter exactly once")
    offset = max(item.position for item in current) + len(current) + 1
    session.execute(update(CourseLesson).where(CourseLesson.chapter_id == chapter_id).values(position=CourseLesson.position + offset))
    session.expire_all()
    for position, lesson_id in enumerate(ids):
        session.get(CourseLesson, lesson_id).position = position
    _commit(session)


def delete_chapter(session: Session, chapter_id: int) -> None:
    session.delete(_chapter(session, chapter_id))
    _commit(session)


def delete_lesson(session: Session, lesson_id: int) -> None:
    session.delete(_lesson(session, lesson_id))
    _commit(session)

"""Transactional course-content operations."""

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.course_models import CourseChapter, CourseLesson, CourseLessonQuestion, CourseMaterial
from app.course_schemas import ChapterCreate, ChapterPatch, LessonCreate, LessonPatch, MaterialCreate, MaterialPatch
from app.models import Question
from app.services.course_material_storage import StorageOperationError, VerifiedMaterialFile
from app.services.notifications import create_notifications, eligible_student_ids


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


def _material(session: Session, material_id: int, *, lock: bool = False) -> CourseMaterial:
    statement = select(CourseMaterial).where(CourseMaterial.id == material_id)
    if lock:
        statement = statement.with_for_update()
    material = session.scalar(statement)
    if material is None:
        raise HTTPException(404, "Material not found")
    return material


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


def _read_public_material(material: CourseMaterial) -> dict:
    return {
        "id": material.id, "title": material.title, "description": material.description,
        "filename": material.original_filename, "media_type": material.media_type,
        "size_bytes": material.size_bytes, "position": material.position,
    }


def read_lesson(lesson: CourseLesson, *, include_status: bool, published_only: bool = False) -> dict:
    result = {
        "id": lesson.id, "chapter_id": lesson.chapter_id, "title": lesson.title, "slug": lesson.slug,
        "content": lesson.content, "position": lesson.position, "created_at": lesson.created_at,
        "updated_at": lesson.updated_at,
        "questions": [{"question_id": item.question_id, "position": item.position} for item in lesson.questions],
        "materials": [
            _read_public_material(item) for item in lesson.materials
            if _storage_ready(item) and (not published_only or item.status == "published")
        ],
    }
    if include_status:
        result["status"] = lesson.status
    return result


def read_chapter(chapter: CourseChapter, *, include_status: bool, published_only: bool = False) -> dict:
    lessons = [item for item in chapter.lessons if not published_only or item.status == "published"]
    result = {
        "id": chapter.id, "title": chapter.title, "slug": chapter.slug, "position": chapter.position,
        "created_at": chapter.created_at, "updated_at": chapter.updated_at,
        "lessons": [read_lesson(item, include_status=include_status, published_only=published_only) for item in lessons],
        "materials": [
            _read_public_material(item) for item in chapter.materials
            if _storage_ready(item) and (not published_only or item.status == "published")
        ],
    }
    if include_status:
        result["status"] = chapter.status
    return result


def list_chapters(session: Session, *, published_only: bool) -> list[dict]:
    statement = select(CourseChapter).options(
        selectinload(CourseChapter.materials),
        selectinload(CourseChapter.lessons).selectinload(CourseLesson.questions),
        selectinload(CourseChapter.lessons).selectinload(CourseLesson.materials),
    )
    if published_only:
        statement = statement.where(CourseChapter.status == "published")
    chapters = session.scalars(statement.order_by(CourseChapter.position, CourseChapter.id)).all()
    return [read_chapter(item, include_status=not published_only, published_only=published_only) for item in chapters]


def published_lesson(session: Session, lesson_id: int) -> dict:
    statement = (
        select(CourseLesson).join(CourseChapter)
        .where(CourseLesson.id == lesson_id, CourseLesson.status == "published", CourseChapter.status == "published")
        .options(selectinload(CourseLesson.questions), selectinload(CourseLesson.materials))
    )
    lesson = session.scalar(statement)
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    return read_lesson(lesson, include_status=False, published_only=True)


def _storage_ready(material: CourseMaterial) -> bool:
    values = (material.storage_key, material.original_filename, material.media_type, material.size_bytes, material.sha256)
    return all(value is not None for value in values)


def read_material(material: CourseMaterial) -> dict:
    return {
        "id": material.id,
        "chapter_id": material.chapter_id,
        "lesson_id": material.lesson_id,
        "title": material.title,
        "description": material.description,
        "filename": material.original_filename,
        "media_type": material.media_type,
        "size_bytes": material.size_bytes,
        "sha256": material.sha256,
        "storage_ready": _storage_ready(material),
        "status": material.status,
        "position": material.position,
        "created_by_id": material.created_by_id,
        "created_at": material.created_at,
        "updated_at": material.updated_at,
    }


def list_materials(session: Session) -> list[dict]:
    materials = session.scalars(
        select(CourseMaterial).order_by(CourseMaterial.chapter_id, CourseMaterial.lesson_id, CourseMaterial.position, CourseMaterial.id)
    ).all()
    return [read_material(material) for material in materials]


def create_material(session: Session, payload: MaterialCreate, actor_user_id: int) -> CourseMaterial:
    values = payload.model_dump()
    if payload.chapter_id is not None:
        _chapter(session, payload.chapter_id)
    else:
        _lesson(session, payload.lesson_id or 0)
    material = CourseMaterial(**values, created_by_id=actor_user_id)
    session.add(material)
    _commit(session)
    session.refresh(material)
    return material


def update_material(session: Session, material_id: int, payload: MaterialPatch) -> CourseMaterial:
    material = _material(session, material_id)
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(material, name, value)
    _commit(session)
    session.refresh(material)
    return material


def _material_parent_is_published(session: Session, material: CourseMaterial) -> bool:
    if material.chapter_id is not None:
        return _chapter(session, material.chapter_id, lock=True).status == "published"
    lesson = _lesson(session, material.lesson_id or 0, lock=True)
    return lesson.status == "published" and _chapter(session, lesson.chapter_id, lock=True).status == "published"


def material_visible_to_student(session: Session, material_id: int) -> CourseMaterial:
    """Return only a material whose own and containing content are published."""
    material = _material(session, material_id)
    if material.status != "published" or not _storage_ready(material):
        raise HTTPException(404, "Material not found")
    if material.chapter_id is not None:
        visible = _chapter(session, material.chapter_id).status == "published"
    else:
        lesson = _lesson(session, material.lesson_id or 0)
        visible = lesson.status == "published" and _chapter(session, lesson.chapter_id).status == "published"
    if not visible:
        raise HTTPException(404, "Material not found")
    return material


def managed_material(session: Session, material_id: int) -> CourseMaterial:
    return _material(session, material_id)


def upload_material_file(session: Session, material_id: int, file: VerifiedMaterialFile, storage) -> CourseMaterial:
    """Write one verified object and atomically attach its metadata or remove it."""
    material = _material(session, material_id, lock=True)
    if material.status != "draft":
        raise HTTPException(409, "Published materials cannot be replaced")
    if _storage_ready(material):
        raise HTTPException(409, "A material file is already attached")
    key = storage.new_key()
    try:
        # Google Drive assigns an opaque file ID after creation. It remains a
        # private implementation detail and is persisted only after success.
        stored_key = storage.put(key, file) or key
    except StorageOperationError:
        # A timeout may occur after a remote write; best-effort cleanup keeps
        # an unreferenced private object from accumulating.
        try:
            storage.delete(key)
        except StorageOperationError:
            pass
        raise HTTPException(502, "Material storage is temporarily unavailable") from None
    material.storage_key = stored_key
    material.original_filename = file.filename
    material.media_type = file.media_type
    material.size_bytes = file.size_bytes
    material.sha256 = file.sha256
    try:
        _commit(session)
    except HTTPException:
        try:
            storage.delete(stored_key)
        except StorageOperationError:
            pass  # The object is inaccessible without a committed database reference.
        raise
    session.refresh(material)
    return material


def publish_material(session: Session, material_id: int, actor_user_id: int | None = None) -> CourseMaterial:
    material = _material(session, material_id, lock=True)
    if not _storage_ready(material):
        raise HTTPException(409, "Upload a verified material file before publishing")
    if not _material_parent_is_published(session, material):
        raise HTTPException(409, "Publish the containing course content before publishing its material")
    newly_published = material.status != "published"
    material.status = "published"
    if newly_published:
        if material.chapter_id is not None:
            link = "/student/course"
        else:
            link = f"/student/course?lesson={material.lesson_id}"
        create_notifications(
            session,
            recipient_user_ids=eligible_student_ids(session),
            actor_user_id=actor_user_id,
            kind="COURSE_MATERIAL_PUBLISHED",
            dedupe_key=f"course-material:{material.id}:published",
            payload={"title": "New course material", "resource_id": material.id},
            link=link,
        )
    _commit(session)
    session.refresh(material)
    return material


def unpublish_material(session: Session, material_id: int) -> CourseMaterial:
    material = _material(session, material_id)
    material.status = "draft"
    _commit(session)
    session.refresh(material)
    return material


def reorder_materials(session: Session, *, chapter_id: int | None, lesson_id: int | None, ids: list[int]) -> None:
    if (chapter_id is None) == (lesson_id is None):
        raise HTTPException(422, "Provide exactly one material container")
    if chapter_id is not None:
        _chapter(session, chapter_id, lock=True)
        condition = CourseMaterial.chapter_id == chapter_id
    else:
        _lesson(session, lesson_id or 0, lock=True)
        condition = CourseMaterial.lesson_id == lesson_id
    current = session.scalars(select(CourseMaterial).where(condition).order_by(CourseMaterial.id).with_for_update()).all()
    if {item.id for item in current} != set(ids):
        raise HTTPException(422, "Material ordering must include every material in the container exactly once")
    offset = max(item.position for item in current) + len(current) + 1
    session.execute(update(CourseMaterial).where(condition).values(position=CourseMaterial.position + offset))
    session.expire_all()
    for position, material_id in enumerate(ids):
        session.get(CourseMaterial, material_id).position = position
    _commit(session)


def delete_material(session: Session, material_id: int, storage=None) -> None:
    """Delete an owned remote file before its metadata, with retry reconciliation."""
    material = _material(session, material_id, lock=True)
    storage_key = material.storage_key
    if storage_key:
        if storage is None:
            session.rollback()
            raise HTTPException(503, "Material storage is unavailable")
        try:
            storage.delete(storage_key)
        except StorageOperationError:
            session.rollback()
            raise HTTPException(502, "Material storage is temporarily unavailable") from None
    session.delete(material)
    try:
        _commit(session)
    except HTTPException:
        # The private object may already be deleted. The row remains after the
        # rollback; retrying this operation treats a missing object as cleaned up.
        raise HTTPException(503, "Material deletion could not be completed; retry it") from None
    except SQLAlchemyError:
        session.rollback()
        # The private object may already be deleted. The row remains after the
        # rollback; retrying this operation treats a missing object as cleaned up.
        raise HTTPException(503, "Material deletion could not be completed; retry it") from None


def create_chapter(session: Session, payload: ChapterCreate) -> CourseChapter:
    chapter = CourseChapter(**payload.model_dump())
    session.add(chapter)
    _commit(session)
    session.refresh(chapter)
    return chapter


def update_chapter(session: Session, chapter_id: int, payload: ChapterPatch) -> CourseChapter:
    chapter = _chapter(session, chapter_id)
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(chapter, name, value)
    _commit(session)
    session.refresh(chapter)
    return chapter


def publish_chapter(session: Session, chapter_id: int, actor_user_id: int | None = None) -> CourseChapter:
    chapter = _chapter(session, chapter_id)
    newly_published = chapter.status != "published"
    chapter.status = "published"
    if newly_published:
        create_notifications(
            session,
            recipient_user_ids=eligible_student_ids(session),
            actor_user_id=actor_user_id,
            kind="COURSE_CHAPTER_PUBLISHED",
            dedupe_key=f"course-chapter:{chapter.id}:published",
            payload={"title": "New course chapter", "resource_id": chapter.id},
            link="/student/course",
        )
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


def publish_lesson(session: Session, lesson_id: int, actor_user_id: int | None = None) -> CourseLesson:
    lesson = _lesson(session, lesson_id)
    chapter = _chapter(session, lesson.chapter_id)
    newly_published = lesson.status != "published"
    lesson.status = "published"
    if newly_published and chapter.status == "published":
        create_notifications(
            session,
            recipient_user_ids=eligible_student_ids(session),
            actor_user_id=actor_user_id,
            kind="COURSE_LESSON_PUBLISHED",
            dedupe_key=f"course-lesson:{lesson.id}:published",
            payload={"title": "New course lesson", "resource_id": lesson.id},
            link=f"/student/course?lesson={lesson.id}",
        )
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

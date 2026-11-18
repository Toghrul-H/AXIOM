from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import get_current_user, manager_user, student_user
from app.auth_models import User
from app.course_schemas import (
    ChapterCreate, ChapterPatch, ChapterRead, LessonCreate, LessonPatch, LessonRead,
    MaterialCreate, MaterialPatch, MaterialRead, OrderUpdate,
)
from app.database import get_session
from app.services import course
from app.services.course_material_storage import (
    MaterialValidationError, StorageConfigurationError, StorageOperationError,
    is_inline_preview_type, required_private_storage, validate_material_upload,
)
from app.config import get_settings

router = APIRouter(prefix="/course", tags=["Course"])
DB = Annotated[Session, Depends(get_session)]
Manager = Annotated[User, Depends(manager_user)]
Student = Annotated[User, Depends(student_user)]
Authenticated = Annotated[User, Depends(get_current_user)]
Id = Annotated[int, Path(gt=0)]


def _material_for_user(session: Session, material_id: int, actor: User):
    if actor.role in {"LECTURER", "ADMIN"}:
        return course.managed_material(session, material_id)
    if actor.role == "STUDENT":
        return course.material_visible_to_student(session, material_id)
    raise HTTPException(404, "Material not found")


def _storage_or_unavailable():
    try:
        return required_private_storage()
    except StorageConfigurationError:
        raise HTTPException(503, "Material storage is unavailable") from None


async def _read_material_upload(request: Request) -> bytes:
    limit = get_settings().materials_max_upload_bytes
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(413, "Material file exceeds the configured size limit")
    return bytes(body)


def _serve_material(material, *, inline: bool) -> Response:
    if not material.storage_key or not material.media_type or material.size_bytes is None or not material.sha256:
        raise HTTPException(404, "Material file is not available")
    storage = _storage_or_unavailable()
    try:
        content = storage.get(material.storage_key, max_bytes=material.size_bytes)
    except StorageOperationError:
        raise HTTPException(502, "Material file is unavailable") from None
    if len(content) != material.size_bytes:
        raise HTTPException(502, "Material file is unavailable")
    import hashlib
    if hashlib.sha256(content).hexdigest() != material.sha256:
        raise HTTPException(502, "Material file is unavailable")
    media_type = material.media_type or "application/octet-stream"
    if inline and media_type == "text/markdown":
        media_type = "text/plain; charset=utf-8"
    elif media_type.startswith("text/"):
        media_type = f"{media_type}; charset=utf-8"
    disposition = "inline" if inline else "attachment"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{material.original_filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/chapters", response_model=list[ChapterRead], response_model_exclude_none=True)
def chapters(session: DB, actor: Student):
    return course.list_chapters(session, published_only=True)


@router.get("/lessons/{lesson_id}", response_model=LessonRead, response_model_exclude_none=True)
def lesson(lesson_id: Id, session: DB, actor: Student):
    return course.published_lesson(session, lesson_id)


@router.get("/manage/chapters", response_model=list[ChapterRead])
def managed_chapters(session: DB, actor: Manager):
    return course.list_chapters(session, published_only=False)


@router.get("/manage/materials", response_model=list[MaterialRead])
def managed_materials(session: DB, actor: Manager):
    return course.list_materials(session)


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
    return course.read_chapter(course.publish_chapter(session, chapter_id, actor.id), include_status=True)


@router.post("/chapters/{chapter_id}/unpublish", response_model=ChapterRead)
def unpublish_chapter(chapter_id: Id, session: DB, actor: Manager):
    return course.read_chapter(course.unpublish_chapter(session, chapter_id), include_status=True)


@router.post("/lessons", response_model=LessonRead, status_code=status.HTTP_201_CREATED)
def create_lesson(payload: LessonCreate, session: DB, actor: Manager):
    return course.read_lesson(course.create_lesson(session, payload), include_status=True)


@router.post("/materials", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
def create_material(payload: MaterialCreate, session: DB, actor: Manager):
    return course.read_material(course.create_material(session, payload, actor.id))


@router.put("/materials/{material_id}/file", response_model=MaterialRead)
async def upload_material_file(material_id: Id, request: Request, session: DB, actor: Manager):
    content = await _read_material_upload(request)
    try:
        file = validate_material_upload(
            request.headers.get("X-Material-Filename"), request.headers.get("Content-Type"), content,
            max_bytes=get_settings().materials_max_upload_bytes,
        )
    except MaterialValidationError as error:
        raise HTTPException(422, str(error)) from None
    return course.read_material(course.upload_material_file(session, material_id, file, _storage_or_unavailable()))


@router.patch("/materials/{material_id}", response_model=MaterialRead)
def update_material(material_id: Id, payload: MaterialPatch, session: DB, actor: Manager):
    return course.read_material(course.update_material(session, material_id, payload))


@router.delete("/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(material_id: Id, session: DB, actor: Manager):
    material = course.managed_material(session, material_id)
    storage = _storage_or_unavailable() if material.storage_key else None
    course.delete_material(session, material_id, storage)


@router.post("/materials/{material_id}/publish", response_model=MaterialRead)
def publish_material(material_id: Id, session: DB, actor: Manager):
    return course.read_material(course.publish_material(session, material_id, actor.id))


@router.post("/materials/{material_id}/unpublish", response_model=MaterialRead)
def unpublish_material(material_id: Id, session: DB, actor: Manager):
    return course.read_material(course.unpublish_material(session, material_id))


@router.get("/materials/{material_id}/download")
def download_material(material_id: Id, session: DB, actor: Authenticated):
    return _serve_material(_material_for_user(session, material_id, actor), inline=False)


@router.get("/materials/{material_id}/preview")
def preview_material(material_id: Id, session: DB, actor: Authenticated):
    material = _material_for_user(session, material_id, actor)
    if not is_inline_preview_type(material.media_type or ""):
        raise HTTPException(422, "This material type cannot be previewed inline")
    return _serve_material(material, inline=True)


@router.patch("/lessons/{lesson_id}", response_model=LessonRead)
def update_lesson(lesson_id: Id, payload: LessonPatch, session: DB, actor: Manager):
    return course.read_lesson(course.update_lesson(session, lesson_id, payload), include_status=True)


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lesson(lesson_id: Id, session: DB, actor: Manager):
    course.delete_lesson(session, lesson_id)


@router.post("/lessons/{lesson_id}/publish", response_model=LessonRead)
def publish_lesson(lesson_id: Id, session: DB, actor: Manager):
    return course.read_lesson(course.publish_lesson(session, lesson_id, actor.id), include_status=True)


@router.post("/lessons/{lesson_id}/unpublish", response_model=LessonRead)
def unpublish_lesson(lesson_id: Id, session: DB, actor: Manager):
    return course.read_lesson(course.unpublish_lesson(session, lesson_id), include_status=True)


@router.put("/chapters/{chapter_id}/lessons/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_lessons(chapter_id: Id, payload: OrderUpdate, session: DB, actor: Manager):
    course.reorder_lessons(session, chapter_id, payload.ids)


@router.put("/chapters/{chapter_id}/materials/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_chapter_materials(chapter_id: Id, payload: OrderUpdate, session: DB, actor: Manager):
    course.reorder_materials(session, chapter_id=chapter_id, lesson_id=None, ids=payload.ids)


@router.put("/lessons/{lesson_id}/materials/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_lesson_materials(lesson_id: Id, payload: OrderUpdate, session: DB, actor: Manager):
    course.reorder_materials(session, chapter_id=None, lesson_id=lesson_id, ids=payload.ids)

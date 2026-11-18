"""Focused metadata-only course-material coverage (M20.1)."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError
from sqlalchemy import MetaData, UniqueConstraint, create_engine, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateSchema, DropSchema

from app.auth import manager_user
from app.auth_models import User
from app.course_models import CourseChapter, CourseLesson, CourseMaterial
from app.course_schemas import ChapterCreate, LessonCreate, MaterialCreate, MaterialPatch, OrderUpdate
from app.database import Base, get_engine
from app.models import ResponseType, SkillType, Topic
from app.notification_models import Notification
from app.routers import course as course_routes
from app.services import course
from app.services import course_material_storage
from app.services.course_material_storage import (
    GoogleDriveStorage, GoogleDriveStorageConfig, MaterialValidationError,
    StorageConfigurationError, StorageOperationError, is_inline_preview_type,
    private_object_storage_config, sanitize_filename, validate_material_upload,
)
from app.config import Settings


def sqlite_metadata() -> MetaData:
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        clone = table.to_metadata(metadata)
        for column in clone.columns:
            if isinstance(column.type, JSONB):
                from sqlalchemy import JSON
                column.type = JSON()
        for constraint in clone.constraints:
            if isinstance(constraint, UniqueConstraint) and constraint.name in {"uq_question_options_position", "uq_quiz_questions_position"}:
                constraint.deferrable = None
                constraint.initially = None
    return metadata


@pytest.fixture
def setup():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sqlite_metadata().create_all(engine)
    session = Session(engine)
    session.add_all((Topic(slug="logic", name="Logic", sort_order=1), ResponseType(code="FREE_RESPONSE", label="Free", sort_order=1), SkillType(code="PROOF", label="Proof", sort_order=1)))
    lecturer = User(email="materials-lecturer@example.test", password_hash="x", role="LECTURER", email_verified=True)
    student = User(email="materials-student@example.test", password_hash="x", role="STUDENT", email_verified=True)
    session.add_all((lecturer, student))
    session.commit()
    yield session, lecturer, student
    session.close()
    engine.dispose()


def test_material_metadata_authorization_ordering_and_visibility_gate(setup):
    session, lecturer, student = setup
    with pytest.raises(HTTPException) as error:
        manager_user(student)
    assert error.value.status_code == 403
    chapter = course.create_chapter(session, ChapterCreate(title="Sets", slug="sets-materials", position=0))
    lesson = course.create_lesson(session, LessonCreate(chapter_id=chapter.id, title="Set notation", slug="set-notation", content="Content", position=0))
    first = course.create_material(session, MaterialCreate(title="Slides", chapter_id=chapter.id, position=0), lecturer.id)
    second = course.create_material(session, MaterialCreate(title="Worksheet", chapter_id=chapter.id, position=1), lecturer.id)
    lesson_material = course.create_material(session, MaterialCreate(title="Notes", lesson_id=lesson.id, position=0), lecturer.id)
    assert course.read_material(first)["storage_ready"] is False
    with pytest.raises(HTTPException) as error:
        course.publish_material(session, first.id)
    assert error.value.status_code == 409
    # M20.2 will set these fields only after a verified object write.
    first.storage_key = "course-materials/1/slides.pdf"
    first.original_filename = sanitize_filename("Slides 2026.pdf")
    first.media_type = "application/pdf"
    first.size_bytes = 123
    first.sha256 = "a" * 64
    session.commit()
    with pytest.raises(HTTPException) as error:
        course.publish_material(session, first.id)
    assert error.value.status_code == 409  # Parent draft content must remain private.
    course.publish_chapter(session, chapter.id)
    assert course.publish_material(session, first.id).status == "published"
    course.reorder_materials(session, chapter_id=chapter.id, lesson_id=None, ids=[second.id, first.id])
    session.expire_all()
    assert [(item.id, item.position) for item in session.query(CourseMaterial).filter_by(chapter_id=chapter.id).order_by(CourseMaterial.position)] == [(second.id, 0), (first.id, 1)]
    assert session.get(CourseMaterial, lesson_material.id).position == 0
    with pytest.raises(HTTPException) as error:
        course.reorder_materials(session, chapter_id=chapter.id, lesson_id=None, ids=[first.id])
    assert error.value.status_code == 422
    assert course.update_material(session, second.id, MaterialPatch(title="Updated worksheet")).title == "Updated worksheet"


def test_material_schema_and_storage_configuration_are_safe(tmp_path):
    def material_settings(**overrides):
        values = {
            "materials_storage_provider": "disabled",
            "materials_google_drive_folder_id": "",
            "materials_google_drive_token_file": "",
            "materials_google_drive_token_json": "",
        }
        values.update(overrides)
        return Settings(**values)

    with pytest.raises(ValueError):
        MaterialCreate(title="Invalid", position=0)
    with pytest.raises(ValueError):
        MaterialCreate(title="Invalid", chapter_id=1, lesson_id=2, position=0)
    assert sanitize_filename("../../lecture\r\n.pdf") == "lecture.pdf"
    assert private_object_storage_config(material_settings()) is None
    token_file = tmp_path / "drive-token.json"
    token_file.write_text('{"refresh_token": "not-a-real-token"}', encoding="utf-8")
    configured = private_object_storage_config(material_settings(
        materials_storage_provider="google_drive",
        materials_google_drive_folder_id="private_folder_123",
        materials_google_drive_token_file=str(token_file),
    ))
    assert configured is not None and configured.folder_id == "private_folder_123"
    with pytest.raises(StorageConfigurationError):
        private_object_storage_config(material_settings(materials_storage_provider="google_drive"))
    with pytest.raises(StorageConfigurationError):
        private_object_storage_config(material_settings(
            materials_storage_provider="google_drive",
            materials_google_drive_folder_id="private_folder_123",
            materials_google_drive_token_file=str(token_file),
            materials_google_drive_token_json='{"refresh_token": "not-a-real-token"}',
        ))


class FakeStorage:
    def __init__(self, *, fail_put=False, fail_delete=False, stored_key=None):
        self.objects = {}
        self.fail_put = fail_put
        self.fail_delete = fail_delete
        self.stored_key = stored_key
        self.deleted = []

    def new_key(self):
        return "course-materials/random-private-key"

    def put(self, key, file):
        if self.fail_put:
            raise StorageOperationError("test failure")
        self.objects[key] = file.content
        return self.stored_key

    def get(self, key, *, max_bytes):
        if key not in self.objects:
            raise StorageOperationError("not found")
        return self.objects[key]

    def delete(self, key):
        if self.fail_delete:
            raise StorageOperationError("test failure")
        self.deleted.append(key)
        self.objects.pop(key, None)


def test_material_upload_validation_storage_and_student_isolation(setup, monkeypatch):
    session, lecturer, student = setup
    chapter = course.create_chapter(session, ChapterCreate(title="Logic", slug="logic-material-upload", position=0))
    material = course.create_material(session, MaterialCreate(title="Handout", chapter_id=chapter.id, position=0), lecturer.id)
    valid = validate_material_upload("handout.pdf", "application/pdf", b"%PDF-1.7\ncontent", max_bytes=1024)
    storage = FakeStorage()
    updated = course.upload_material_file(session, material.id, valid, storage)
    assert updated.storage_key == "course-materials/random-private-key"
    assert updated.sha256 == valid.sha256 and updated.original_filename == "handout.pdf"
    with pytest.raises(HTTPException) as error:
        course.material_visible_to_student(session, material.id)
    assert error.value.status_code == 404
    course.publish_chapter(session, chapter.id)
    assert course.publish_material(session, material.id, lecturer.id).status == "published"
    notice = session.scalar(select(Notification).where(Notification.kind == "COURSE_MATERIAL_PUBLISHED"))
    assert notice is not None
    assert notice.recipient_user_id == student.id and notice.actor_user_id == lecturer.id
    assert notice.link == "/student/course" and notice.payload == {"title": "New course material", "resource_id": material.id}
    course.publish_material(session, material.id, lecturer.id)
    assert session.query(Notification).filter_by(kind="COURSE_MATERIAL_PUBLISHED").count() == 1
    lesson = course.create_lesson(session, LessonCreate(chapter_id=chapter.id, title="Proofs", slug="proofs-material", content="Proofs", position=0))
    lesson_material = course.create_material(session, MaterialCreate(title="Lesson notes", lesson_id=lesson.id, position=0), lecturer.id)
    lesson_material.storage_key = "course-materials/lesson-notes"
    lesson_material.original_filename = "lesson-notes.txt"
    lesson_material.media_type = "text/plain"
    lesson_material.size_bytes = 5
    lesson_material.sha256 = "b" * 64
    session.commit()
    course.publish_lesson(session, lesson.id, lecturer.id)
    course.publish_material(session, lesson_material.id, lecturer.id)
    lesson_notice = next(item for item in session.scalars(select(Notification).where(Notification.kind == "COURSE_MATERIAL_PUBLISHED")) if item.payload["resource_id"] == lesson_material.id)
    assert lesson_notice.link == f"/student/course?lesson={lesson.id}"
    assert course.material_visible_to_student(session, material.id).id == material.id
    public = course.list_chapters(session, published_only=True)
    assert public[0]["materials"] == [{
        "id": material.id, "title": "Handout", "description": None,
        "filename": "handout.pdf", "media_type": "application/pdf",
        "size_bytes": len(valid.content), "position": 0,
    }]
    assert "sha256" not in public[0]["materials"][0]
    monkeypatch.setattr(course_routes, "required_private_storage", lambda: storage)
    preview = course_routes._serve_material(material, inline=True)
    assert preview.body == valid.content
    assert preview.headers["content-disposition"] == 'inline; filename="handout.pdf"'
    assert preview.headers["x-content-type-options"] == "nosniff"
    storage.objects.clear()
    with pytest.raises(HTTPException) as error:
        course_routes._serve_material(material, inline=False)
    assert error.value.status_code == 502
    with pytest.raises(HTTPException) as error:
        course.upload_material_file(session, material.id, valid, storage)
    assert error.value.status_code == 409

    failed = course.create_material(session, MaterialCreate(title="Broken", chapter_id=chapter.id, position=1), lecturer.id)
    with pytest.raises(HTTPException) as error:
        course.upload_material_file(session, failed.id, valid, FakeStorage(fail_put=True))
    assert error.value.status_code == 502
    session.refresh(failed)
    assert failed.storage_key is None


class FakeGoogleRequest:
    def __init__(self, result):
        self.result = result

    def execute(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeGoogleFiles:
    def __init__(self):
        self.create_calls = []
        self.get_calls = []
        self.delete_calls = []
        self.content = b"%PDF-1.7\ncontent"
        self.created_id = "opaque-drive-file-id"
        self.delete_result = None

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return FakeGoogleRequest({"id": self.created_id})

    def get_media(self, **kwargs):
        self.get_calls.append(kwargs)
        return FakeGoogleRequest(self.content)

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        return FakeGoogleRequest({
            "id": kwargs["fileId"],
            "name": "axiom-material-test",
            "parents": ["private_folder_123"],
            "trashed": False,
        })

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)
        return FakeGoogleRequest(self.delete_result)


def test_google_drive_storage_uses_opaque_file_ids_and_never_shares(monkeypatch):
    files = FakeGoogleFiles()
    monkeypatch.setattr(course_material_storage, "_load_drive_credentials", lambda config: object())
    monkeypatch.setattr(
        course_material_storage,
        "build",
        lambda *args, **kwargs: type("DriveService", (), {"files": lambda self: files})(),
    )
    storage = GoogleDriveStorage(GoogleDriveStorageConfig("private_folder_123", "{}"))
    file = validate_material_upload("handout.pdf", "application/pdf", b"%PDF-1.7\ncontent", max_bytes=1024)
    generated_name = storage.new_key()
    file_id = storage.put(generated_name, file)

    assert file_id == "opaque-drive-file-id"
    assert files.create_calls[0]["body"] == {
        "name": generated_name,
        "parents": ["private_folder_123"],
        "mimeType": "application/pdf",
    }
    assert storage.get(file_id, max_bytes=1024) == file.content
    storage.delete(file_id)
    assert files.get_calls == [
        {"fileId": file_id},
        {"fileId": file_id, "fields": "id,name,parents,trashed"},
    ]
    assert files.delete_calls == [{"fileId": file_id}]


def test_google_drive_failures_are_safe_and_returned_ids_are_persisted(setup, monkeypatch):
    files = FakeGoogleFiles()
    monkeypatch.setattr(course_material_storage, "_load_drive_credentials", lambda config: object())
    monkeypatch.setattr(
        course_material_storage,
        "build",
        lambda *args, **kwargs: type("DriveService", (), {"files": lambda self: files})(),
    )
    storage = GoogleDriveStorage(GoogleDriveStorageConfig("private_folder_123", "{}"))
    files.created_id = "actual-drive-id"
    session, lecturer, _student = setup
    chapter = course.create_chapter(session, ChapterCreate(title="Drive", slug="drive-material", position=0))
    material = course.create_material(session, MaterialCreate(title="Handout", chapter_id=chapter.id, position=0), lecturer.id)
    file = validate_material_upload("handout.pdf", "application/pdf", b"%PDF-1.7\ncontent", max_bytes=1024)
    assert course.upload_material_file(session, material.id, file, storage).storage_key == "actual-drive-id"

    files.content = RuntimeError("provider unavailable")
    with pytest.raises(StorageOperationError):
        storage.get("actual-drive-id", max_bytes=1024)
    files.delete_result = RuntimeError("provider unavailable")
    with pytest.raises(StorageOperationError):
        storage.delete("actual-drive-id")

    monkeypatch.setattr(course_material_storage, "build", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError()))
    with pytest.raises(StorageOperationError):
        storage.get("actual-drive-id", max_bytes=1024)


def test_material_deletion_removes_owned_object_and_preserves_metadata_on_failure(setup, monkeypatch):
    session, lecturer, _student = setup
    chapter = course.create_chapter(session, ChapterCreate(title="Delete", slug="delete-material", position=0))
    file = validate_material_upload("handout.pdf", "application/pdf", b"%PDF-1.7\ncontent", max_bytes=1024)
    storage = FakeStorage(stored_key="opaque-drive-id")
    material = course.create_material(session, MaterialCreate(title="Handout", chapter_id=chapter.id, position=0), lecturer.id)
    course.upload_material_file(session, material.id, file, storage)
    course.delete_material(session, material.id, storage)
    assert session.get(CourseMaterial, material.id) is None
    assert storage.deleted == ["opaque-drive-id"]

    failed = course.create_material(session, MaterialCreate(title="Retry", chapter_id=chapter.id, position=0), lecturer.id)
    course.upload_material_file(session, failed.id, file, FakeStorage(stored_key="provider-failure"))
    failing_storage = FakeStorage(fail_delete=True)
    with pytest.raises(HTTPException) as error:
        course.delete_material(session, failed.id, failing_storage)
    assert error.value.status_code == 502
    assert session.get(CourseMaterial, failed.id) is not None

    retry = course.create_material(session, MaterialCreate(title="Database", chapter_id=chapter.id, position=1), lecturer.id)
    retry_storage = FakeStorage(stored_key="commit-failure")
    course.upload_material_file(session, retry.id, file, retry_storage)
    original_commit = course._commit
    def failed_commit(current_session):
        current_session.rollback()
        raise OperationalError("COMMIT", {}, RuntimeError("test database failure"))
    monkeypatch.setattr(course, "_commit", failed_commit)
    with pytest.raises(HTTPException) as error:
        course.delete_material(session, retry.id, retry_storage)
    assert error.value.status_code == 503
    assert retry_storage.deleted == ["commit-failure"]
    assert session.get(CourseMaterial, retry.id) is not None
    monkeypatch.setattr(course, "_commit", original_commit)


def test_material_file_type_validation_and_preview_policy():
    valid = validate_material_upload("notes.md", "text/plain", b"# Sets\nA \\ B", max_bytes=1024)
    assert valid.media_type == "text/markdown" and is_inline_preview_type(valid.media_type)
    assert is_inline_preview_type("application/pdf") and not is_inline_preview_type("application/msword")
    for filename, media_type, content in (
        ("unsafe.svg", "image/svg+xml", b"<svg />"),
        ("page.pdf", "image/png", b"%PDF-1.7"),
        ("page.pdf", "application/pdf", b"<html>not a PDF</html>"),
        ("notes.txt", "text/plain", b"bad\x00text"),
    ):
        with pytest.raises(MaterialValidationError):
            validate_material_upload(filename, media_type, content, max_bytes=1024)


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Set RUN_POSTGRES_TESTS=1 for an isolated PostgreSQL schema")
def test_course_material_migration_round_trip():
    schema = f"dmi_materials_{uuid4().hex}"
    with get_engine().begin() as connection:
        connection.execute(CreateSchema(schema))
        try:
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "0027")
            connection.execute(text("INSERT INTO users (email, password_hash) VALUES ('pre-material@example.test', 'x')"))
            command.upgrade(config, "0028")
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0028"
            assert connection.execute(text("SELECT to_regclass('course_materials')")).scalar() == "course_materials"
            assert connection.execute(text("SELECT count(*) FROM users WHERE email = 'pre-material@example.test' ")).scalar() == 1
            assert connection.execute(text("SELECT count(*) FROM pg_indexes WHERE schemaname = current_schema() AND indexname IN ('uq_course_materials_chapter_position', 'uq_course_materials_lesson_position')")).scalar() == 2
            command.downgrade(config, "0027")
            assert connection.execute(text("SELECT to_regclass('course_materials')")).scalar() is None
        finally:
            connection.execute(text("SET LOCAL search_path TO public"))
            connection.execute(DropSchema(schema, cascade=True))


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Set RUN_POSTGRES_TESTS=1 for an isolated PostgreSQL schema")
def test_postgres_material_publication_notifies_eligible_students_once():
    schema = f"dmi_material_notice_{uuid4().hex}"
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "0028")
    connection = engine.connect()
    connection.execute(text(f'SET search_path TO "{schema}", public'))
    connection.commit()
    session = Session(connection)
    try:
        lecturer = User(email="material-notice-staff@example.test", password_hash="x", role="LECTURER", email_verified=True)
        eligible = User(email="material-notice-student@example.test", password_hash="x", role="STUDENT", email_verified=True)
        inactive = User(email="material-notice-inactive@example.test", password_hash="x", role="STUDENT", is_active=False, email_verified=True)
        session.add_all((lecturer, eligible, inactive))
        session.flush()
        chapter = CourseChapter(title="Logic", slug="logic-material-notice", position=0, status="published")
        session.add(chapter)
        session.flush()
        material = CourseMaterial(
            chapter_id=chapter.id, title="Notes", original_filename="notes.pdf", storage_key="course-materials/notice",
            media_type="application/pdf", size_bytes=8, sha256="c" * 64, position=0, created_by_id=lecturer.id,
        )
        session.add(material)
        session.commit()
        course.publish_material(session, material.id, lecturer.id)
        course.publish_material(session, material.id, lecturer.id)
        notices = session.scalars(select(Notification).where(Notification.kind == "COURSE_MATERIAL_PUBLISHED")).all()
        assert len(notices) == 1
        assert notices[0].recipient_user_id == eligible.id
        assert notices[0].link == "/student/course"
    finally:
        session.close()
        connection.execute(text("SET search_path TO public"))
        connection.commit()
        connection.close()
        with engine.begin() as cleanup:
            cleanup.execute(DropSchema(schema, cascade=True))

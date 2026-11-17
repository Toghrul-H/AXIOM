from sqlalchemy import JSON, MetaData, UniqueConstraint, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
import pytest
from fastapi import HTTPException

from app.auth import manager_user, student_user
from app.auth_models import User
from app.course_models import CourseChapter, CourseLesson
from app.course_schemas import ChapterCreate, LessonCreate, LessonPatch, OrderUpdate
from app.database import Base
from app.models import Question, ResponseType, SkillType, Topic
from app.routers.course import router as course_router
from app.services import course


def sqlite_metadata() -> MetaData:
    metadata = MetaData()
    for table in Base.metadata.sorted_tables:
        clone = table.to_metadata(metadata)
        for column in clone.columns:
            if isinstance(column.type, JSONB):
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
    topic = Topic(slug="logic", name="Logic", sort_order=1)
    session.add_all((topic, ResponseType(code="FREE_RESPONSE", label="Free response", sort_order=1), SkillType(code="PROOF", label="Proof", sort_order=1)))
    session.flush()
    question = Question(topic_id=topic.id, difficulty="easy", response_type="FREE_RESPONSE", skill_type="PROOF", question_text="Show $A \\subseteq B$.", expected_answer="A proof.", explanation="Use inclusion.")
    lecturer = User(email="course-lecturer@example.test", password_hash="x", role="LECTURER", email_verified=True)
    student = User(email="course-student@example.test", password_hash="x", role="STUDENT", email_verified=True)
    demonstrator = User(email="course-demo@example.test", password_hash="x", role="DEMONSTRATOR", email_verified=True)
    session.add_all((question, lecturer, student, demonstrator))
    session.commit()
    yield session, question, lecturer, student, demonstrator
    session.close()
    engine.dispose()


def chapter_payload(position=0):
    return ChapterCreate(title="Sets", slug="sets", position=position)


def lesson_payload(chapter_id, question_id, position=0):
    return LessonCreate(chapter_id=chapter_id, title="Subsets", slug="subsets", content="Learn $A \\subseteq B$ safely.", position=position, questions=[{"question_id": question_id}])


def test_course_permissions_and_published_visibility(setup):
    session, question, lecturer, student, demonstrator = setup
    assert manager_user(lecturer) is lecturer
    assert student_user(student) is student
    for user in (student, demonstrator):
        with pytest.raises(HTTPException) as error:
            manager_user(user)
        assert error.value.status_code == 403

    chapter = course.create_chapter(session, chapter_payload())
    lesson = course.create_lesson(session, lesson_payload(chapter.id, question.id))
    assert course.list_chapters(session, published_only=True) == []
    managed = course.list_chapters(session, published_only=False)
    assert managed[0]["status"] == "draft" and managed[0]["lessons"][0]["questions"] == [{"question_id": question.id, "position": 0}]

    course.publish_lesson(session, lesson.id)
    assert course.list_chapters(session, published_only=True) == []
    course.publish_chapter(session, chapter.id)
    public = course.list_chapters(session, published_only=True)
    assert public[0]["lessons"][0]["content"] == "Learn $A \\subseteq B$ safely."
    assert "status" not in public[0] and "expected_answer" not in public[0]["lessons"][0]["questions"][0]
    course.unpublish_lesson(session, lesson.id)
    assert course.list_chapters(session, published_only=True)[0]["lessons"] == []
    course.publish_lesson(session, lesson.id)
    course.unpublish_chapter(session, chapter.id)
    assert course.list_chapters(session, published_only=True) == []
    with pytest.raises(HTTPException) as error:
        course.published_lesson(session, lesson.id)
    assert error.value.status_code == 404


def test_course_crud_ordering_and_question_validation(setup):
    session, question, lecturer, _, _ = setup
    first = course.create_chapter(session, chapter_payload(0))
    second = course.create_chapter(session, ChapterCreate(title="Logic", slug="logic-course", position=1))
    unrelated = course.create_chapter(session, ChapterCreate(title="Graphs", slug="graphs-course", position=2))
    first_lesson = course.create_lesson(session, lesson_payload(first.id, question.id, 0))
    second_lesson = course.create_lesson(session, LessonCreate(chapter_id=first.id, title="Relations", slug="relations", content="Relations.", position=1))
    unrelated_lesson = course.create_lesson(session, LessonCreate(chapter_id=unrelated.id, title="Graphs", slug="graphs", content="Graphs.", position=0))
    # Gapped positions can arise after deletion; reordering must not collide transiently.
    second.position = 5
    first_lesson.position = 5
    session.commit()
    course.reorder_chapters(session, OrderUpdate(ids=[second.id, first.id, unrelated.id]).ids)
    course.reorder_lessons(session, first.id, OrderUpdate(ids=[second_lesson.id, first_lesson.id]).ids)
    session.expire_all()
    assert [(item.id, item.position) for item in session.query(CourseChapter).order_by(CourseChapter.position)] == [(second.id, 0), (first.id, 1), (unrelated.id, 2)]
    assert [(item.id, item.position) for item in session.query(CourseLesson).filter_by(chapter_id=first.id).order_by(CourseLesson.position)] == [(second_lesson.id, 0), (first_lesson.id, 1)]
    assert session.get(CourseLesson, unrelated_lesson.id).position == 0
    updated = course.update_lesson(session, first_lesson.id, LessonPatch(content="Updated $\\alpha$ text.", questions=[]))
    assert updated.questions == []
    with pytest.raises(HTTPException) as error:
        course.create_lesson(session, LessonCreate(chapter_id=first.id, title="Invalid", slug="invalid", content="Invalid.", position=2, questions=[{"question_id": 999999}]))
    assert error.value.status_code == 422
    question.is_active = False
    session.commit()
    with pytest.raises(HTTPException) as error:
        course.update_lesson(session, first_lesson.id, LessonPatch(questions=[{"question_id": question.id}]))
    assert error.value.status_code == 422
    with pytest.raises(ValueError):
        LessonCreate.model_validate({**lesson_payload(first.id, question.id).model_dump(), "questions": [{"question_id": question.id}] * 2})
    with pytest.raises(HTTPException) as error:
        course.reorder_chapters(session, [first.id])
    assert error.value.status_code == 422


def test_draft_lesson_is_not_addressable_by_students(setup):
    session, question, _, _, _ = setup
    chapter = course.create_chapter(session, chapter_payload())
    lesson = course.create_lesson(session, lesson_payload(chapter.id, question.id))
    course.publish_chapter(session, chapter.id)
    with pytest.raises(HTTPException) as error:
        course.published_lesson(session, lesson.id)
    assert error.value.status_code == 404
    course.publish_lesson(session, lesson.id)
    assert course.published_lesson(session, lesson.id)["id"] == lesson.id


def test_course_deletion_removes_only_the_selected_content(setup):
    session, question, _, _, _ = setup
    first = course.create_chapter(session, chapter_payload())
    second = course.create_chapter(session, ChapterCreate(title="Logic", slug="logic-delete", position=1))
    first_lesson = course.create_lesson(session, lesson_payload(first.id, question.id))
    second_lesson = course.create_lesson(session, LessonCreate(chapter_id=second.id, title="Propositions", slug="propositions", content="Logic.", position=0))
    course.delete_lesson(session, first_lesson.id)
    assert session.get(CourseLesson, first_lesson.id) is None
    assert session.get(CourseLesson, second_lesson.id) is not None
    course.delete_chapter(session, first.id)
    assert session.get(CourseChapter, first.id) is None
    assert session.get(CourseChapter, second.id) is not None


def test_course_routes_are_registered_with_expected_methods():
    routes = {(route.path, method) for route in course_router.routes for method in route.methods}
    for expected in {
        ("/course/chapters", "GET"), ("/course/chapters", "POST"),
        ("/course/chapters/reorder", "PUT"), ("/course/lessons", "POST"),
        ("/course/lessons/{lesson_id}", "PATCH"),
        ("/course/chapters/{chapter_id}/lessons/reorder", "PUT"),
    }:
        assert expected in routes
